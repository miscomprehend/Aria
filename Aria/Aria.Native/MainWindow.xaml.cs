using System.Text.Json;
using Microsoft.UI.Windowing;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI;
using Windows.Graphics;
using System.IO;
using Microsoft.UI.Xaml.Media.Imaging;

namespace Aria.Native;

public sealed partial class MainWindow : Window
{
    private readonly AriaDashboardClient _client = new();
    private readonly NativeSetupClient _setupClient = new();
    private readonly string _baseUrl;
    private readonly bool _needsTokenSetup;
    private string _page = "overview";

    public MainWindow()
    {
        InitializeComponent();
        var brandIconPath = Path.Combine(AppContext.BaseDirectory, "aria.png");
        var brandIcon = new BitmapImage(new Uri(brandIconPath, UriKind.Absolute));
        TitleBrandIcon.Source = brandIcon;
        SetupBrandIcon.Source = brandIcon;
        ExtendsContentIntoTitleBar = true;
        SetTitleBar(TitleBar);
        var windowHandle = WinRT.Interop.WindowNative.GetWindowHandle(this);
        var windowId = Win32Interop.GetWindowIdFromWindow(windowHandle);
        var appWindow = AppWindow.GetFromWindowId(windowId);
        _needsTokenSetup = Environment.GetEnvironmentVariable("ARIA_NEEDS_TOKEN_SETUP") == "1";
        appWindow.Resize(_needsTokenSetup ? new SizeInt32(560, 640) : new SizeInt32(1360, 860));
        appWindow.SetIcon(Path.Combine(AppContext.BaseDirectory, "aria.ico"));
        _baseUrl = Environment.GetEnvironmentVariable("ARIA_DASHBOARD_URL") ?? "";
        _ = InitializeAsync();
    }

    private async Task InitializeAsync()
    {
        try
        {
            if (string.IsNullOrWhiteSpace(_baseUrl))
                throw new InvalidOperationException("The desktop launcher did not provide a local dashboard address.");

            if (_needsTokenSetup)
            {
                ConnectionProgress.IsActive = false;
                StatusMessage.Text = "Connect the account Aria should run as.";
                TokenSetupPanel.Visibility = Visibility.Visible;
                return;
            }

            var authToken = Environment.GetEnvironmentVariable("ARIA_ELECTRON_AUTH_TOKEN") ?? "";
            Environment.SetEnvironmentVariable("ARIA_ELECTRON_AUTH_TOKEN", null);
            if (string.IsNullOrWhiteSpace(authToken))
            {
                _client.SetBaseAddress(_baseUrl);
                ConnectionProgress.IsActive = false;
                StatusMessage.Text = "Sign in to the local Aria service.";
                LoginPanel.Visibility = Visibility.Visible;
                return;
            }

            await _client.AuthenticateOwnerAsync(_baseUrl, authToken);
            await LoadIdentityAsync();
            StatusOverlay.Visibility = Visibility.Collapsed;
            await LoadPageAsync("overview");
        }
        catch (Exception error)
        {
            ConnectionProgress.IsActive = false;
            StatusMessage.Text = error.Message;
            RetryButton.Visibility = Visibility.Visible;
        }
    }

    private async void SetupToken_Click(object sender, RoutedEventArgs e)
    {
        var token = SetupToken.Password.Trim();
        if (token.Length == 0)
        {
            StatusMessage.Text = "Enter the account token to continue.";
            return;
        }

        SetupSubmitButton.IsEnabled = false;
        StatusMessage.Text = "Verifying the account and starting your dashboard…";
        try
        {
            var result = await _setupClient.SaveTokenAsync(
                token,
                RememberToken.IsChecked == true);
            SetupToken.Password = "";
            await _client.AuthenticateOwnerAsync(result.DashboardUrl, result.AuthToken);
            await LoadIdentityAsync();
            StatusOverlay.Visibility = Visibility.Collapsed;
            await LoadPageAsync("overview");
        }
        catch (Exception error)
        {
            StatusMessage.Text = error.Message;
            SetupSubmitButton.IsEnabled = true;
        }
    }

    private async void Login_Click(object sender, RoutedEventArgs e)
    {
        var username = LoginUsername.Text.Trim();
        var password = LoginPassword.Password;
        if (username.Length == 0 || password.Length == 0)
        {
            StatusMessage.Text = "Enter your Aria username and password.";
            return;
        }

        try
        {
            StatusMessage.Text = "Signing in…";
            await _client.LoginAsync(username, password, LoginDiscordId.Text.Trim());
            LoginPassword.Password = "";
            await LoadIdentityAsync();
            StatusOverlay.Visibility = Visibility.Collapsed;
            await LoadPageAsync("overview");
        }
        catch (Exception error)
        {
            StatusMessage.Text = error.Message;
        }
    }

    private async void Navigation_Click(object sender, RoutedEventArgs e)
    {
        if (sender is Button { Tag: string page })
            await LoadPageAsync(page);
    }

    private async void Refresh_Click(object sender, RoutedEventArgs e) => await LoadPageAsync(_page);

    private async void Retry_Click(object sender, RoutedEventArgs e)
    {
        RetryButton.Visibility = Visibility.Collapsed;
        ConnectionProgress.IsActive = true;
        StatusMessage.Text = "Signing in to the local dashboard service…";
        await InitializeAsync();
    }

    private async Task LoadPageAsync(string page)
    {
        _page = page;
        PageContent.Children.Clear();
        try
        {
            if (page == "owner")
            {
                PageTitle.Text = "Owner tools";
                PageSubtitle.Text = "Account access and recovery controls";
                await LoadOwnerToolsAsync();
            }
            else if (page == "hosted")
            {
                PageTitle.Text = "Hosted instances";
                PageSubtitle.Text = "Manage the Aria clients attached to your account";
                await LoadHostedAsync();
            }
            else
            {
                PageTitle.Text = "Overview";
                PageSubtitle.Text = "Your Aria runtime at a glance";
                await LoadOverviewAsync();
            }
        }
        catch (Exception error)
        {
            PageContent.Children.Add(new TextBlock
            {
                Text = error.Message,
                TextWrapping = TextWrapping.Wrap,
                Foreground = new Microsoft.UI.Xaml.Media.SolidColorBrush(Microsoft.UI.Colors.Salmon),
            });
        }
    }

    private async Task LoadIdentityAsync()
    {
        using var response = await _client.GetAsync("/api/dash/me");
        var profile = response.RootElement.GetProperty("profile");
        SessionIdentity.Text = ReadText(profile, "username", "Signed in");
        OwnerNavigationButton.Visibility = ReadBoolean(profile, "is_owner")
            ? Visibility.Visible
            : Visibility.Collapsed;
    }

    private async Task LoadOverviewAsync()
    {
        using var summary = await _client.GetAsync("/api/max/system-summary");
        using var bot = await _client.GetAsync("/api/bot");
        var summaryData = summary.RootElement.GetProperty("summary");
        var botData = bot.RootElement.GetProperty("data");

        var connected = ReadBoolean(summaryData, "connected");
        PageContent.Children.Add(CreateMetricGrid(
            ("Gateway", connected ? "Connected" : "Disconnected"),
            ("Uptime", ReadText(summaryData, "uptime", "—")),
            ("Commands", ReadText(summaryData, "commands_total", "0")),
            ("Hosted clients", $"{ReadText(summaryData, "hosted_active", "0")} / {ReadText(summaryData, "hosted_total", "0")}")));
        PageContent.Children.Add(CreateCard("Account", new[]
        {
            ("Username", ReadText(botData, "username", "Aria")),
            ("Account ID", ReadText(botData, "user_id", "—")),
            ("Connection", connected ? "Gateway session active" : "Waiting for gateway connection"),
        }));
        PageContent.Children.Add(CreateCard("Desktop dashboard", new[]
        {
            ("Interface", "Native WinUI"),
            ("Backend", new Uri(_baseUrl).Host),
            ("Rendering", "Windows controls and XAML"),
        }));
    }

    private async Task LoadHostedAsync()
    {
        using var result = await _client.GetAsync("/api/hosted");
        var hosted = result.RootElement.GetProperty("hosted");
        var tokenBox = new PasswordBox { Header = "Discord account token", PasswordRevealMode = PasswordRevealMode.Peek };
        var prefixBox = new TextBox { Header = "Command prefix", Text = ";", Width = 140 };
        var fields = new Grid { ColumnSpacing = 12 };
        fields.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(3, GridUnitType.Star) });
        fields.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        fields.Children.Add(tokenBox);
        Grid.SetColumn(prefixBox, 1);
        fields.Children.Add(prefixBox);
        var form = new StackPanel { Spacing = 10 };
        form.Children.Add(fields);
        var connectButton = new Button { Content = "Connect instance", HorizontalAlignment = HorizontalAlignment.Left };
        form.Children.Add(connectButton);
        PageContent.Children.Add(CreatePanel("Add hosted instance", form));
        connectButton.Click += async (_, _) =>
        {
            connectButton.IsEnabled = false;
            try
            {
                using var response = await _client.PostAsync("/api/hosted/connect", new
                {
                    token = tokenBox.Password,
                    prefix = prefixBox.Text,
                });
                tokenBox.Password = "";
                await LoadPageAsync("hosted");
            }
            catch (Exception error)
            {
                PageContent.Children.Insert(0, new TextBlock
                {
                    Text = error.Message,
                    Foreground = new Microsoft.UI.Xaml.Media.SolidColorBrush(Microsoft.UI.Colors.Salmon),
                    TextWrapping = TextWrapping.Wrap,
                });
                connectButton.IsEnabled = true;
            }
        };

        if (hosted.GetArrayLength() == 0)
        {
            PageContent.Children.Add(CreatePanel("No hosted instances", new TextBlock
            {
                Text = "Connect an account above to add your first hosted instance.",
                Foreground = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaMutedBrush"],
            }));
            return;
        }

        foreach (var instance in hosted.EnumerateArray())
        {
            var reference = ReadText(instance, "token_ref", "");
            var connected = ReadBoolean(instance, "connected");
            var details = new StackPanel { Spacing = 5 };
            details.Children.Add(new TextBlock
            {
                Text = ReadText(instance, "username", "Unknown account"),
                FontSize = 16,
                FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            });
            details.Children.Add(new TextBlock
            {
                Text = $"{(connected ? "Connected" : "Offline")}  ·  {ReadText(instance, "client_type", "unknown")}  ·  Prefix {ReadText(instance, "prefix", ";")}",
                Foreground = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaMutedBrush"],
                FontSize = 12,
            });
            if (!string.IsNullOrWhiteSpace(ReadText(instance, "connection_error", "")))
                details.Children.Add(new TextBlock
                {
                    Text = ReadText(instance, "connection_error", ""),
                    Foreground = new Microsoft.UI.Xaml.Media.SolidColorBrush(Microsoft.UI.Colors.Salmon),
                    TextWrapping = TextWrapping.Wrap,
                    FontSize = 11,
                });

            var actions = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8 };
            var restart = new Button { Content = "Restart" };
            restart.Click += async (_, _) => await RunHostedActionAsync("/api/hosted/restart", reference);
            var disconnect = new Button { Content = "Disconnect" };
            disconnect.Click += async (_, _) => await RunHostedActionAsync("/api/hosted/disconnect", reference);
            actions.Children.Add(restart);
            actions.Children.Add(disconnect);

            var row = new Grid();
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            row.Children.Add(details);
            Grid.SetColumn(actions, 1);
            row.Children.Add(actions);
            PageContent.Children.Add(CreatePanel("Instance", row));
        }
    }

    private async Task LoadOwnerToolsAsync()
    {
        using var response = await _client.GetAsync("/api/owner/summary");
        var data = response.RootElement.GetProperty("data");
        PageContent.Children.Add(CreateMetricGrid(
            ("Accounts", ReadText(data, "total_accounts", "0")),
            ("Admin accounts", ReadText(data, "admin_accounts", "0")),
            ("Pending requests", ReadText(data, "pending_requests", "0")),
            ("Gateway", ReadBoolean(data, "connected") ? "Connected" : "Offline")));
        PageContent.Children.Add(CreateCard("Main account", new[]
        {
            ("Username", ReadText(data, "username", "—")),
            ("Account ID", ReadText(data, "user_id", "—")),
            ("Gateway latency", $"{ReadText(data, "gateway_latency_ms", "—")} ms"),
        }));

        var requests = data.GetProperty("password_reset_requests");
        var queue = new StackPanel { Spacing = 10 };
        if (requests.GetArrayLength() == 0)
        {
            queue.Children.Add(new TextBlock
            {
                Text = "There are no pending password reset requests.",
                Foreground = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaMutedBrush"],
            });
        }
        else
        {
            foreach (var request in requests.EnumerateArray())
            {
                var requestId = ReadText(request, "id", "");
                var details = new StackPanel { Spacing = 4 };
                details.Children.Add(new TextBlock
                {
                    Text = ReadText(request, "username", "Account"),
                    FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
                });
                details.Children.Add(new TextBlock
                {
                    Text = ReadText(request, "reason", "Password reset requested"),
                    Foreground = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaMutedBrush"],
                    TextWrapping = TextWrapping.Wrap,
                });
                var actions = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8 };
                var approve = new Button { Content = "Approve reset" };
                approve.Click += async (_, _) => await ResolvePasswordResetAsync(requestId, true);
                var deny = new Button { Content = "Deny" };
                deny.Click += async (_, _) => await ResolvePasswordResetAsync(requestId, false);
                actions.Children.Add(approve);
                actions.Children.Add(deny);

                var item = new StackPanel { Spacing = 10 };
                item.Children.Add(details);
                item.Children.Add(actions);
                queue.Children.Add(new Border
                {
                    Background = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaRaisedBrush"],
                    BorderBrush = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaBorderBrush"],
                    BorderThickness = new Thickness(1),
                    CornerRadius = new CornerRadius(6),
                    Padding = new Thickness(12),
                    Child = item,
                });
            }
        }
        PageContent.Children.Add(CreatePanel("Password reset requests", queue));

        var accounts = new StackPanel { Spacing = 8 };
        foreach (var account in data.GetProperty("accounts").EnumerateArray().Take(20))
            accounts.Children.Add(new TextBlock
            {
                Text = $"{ReadText(account, "username", "Account")}  ·  {ReadText(account, "role", "user")}",
                Foreground = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaMutedBrush"],
            });
        PageContent.Children.Add(CreatePanel("Recent accounts", accounts));
    }

    private async Task ResolvePasswordResetAsync(string requestId, bool approve)
    {
        try
        {
            using var response = await _client.PostAsync(
                $"/api/dash/requests/{Uri.EscapeDataString(requestId)}/{(approve ? "approve" : "deny")}",
                new { });
            if (approve && response.RootElement.TryGetProperty("password", out var password))
            {
                var passwordText = new TextBlock
                {
                    Text = password.GetString() ?? "",
                    IsTextSelectionEnabled = true,
                    FontFamily = new Microsoft.UI.Xaml.Media.FontFamily("Consolas"),
                };
                var dialog = new ContentDialog
                {
                    Title = "Temporary password generated",
                    Content = passwordText,
                    CloseButtonText = "Done",
                    XamlRoot = PageContent.XamlRoot,
                };
                await dialog.ShowAsync();
            }
            await LoadPageAsync("owner");
        }
        catch (Exception error)
        {
            PageContent.Children.Insert(0, new TextBlock
            {
                Text = error.Message,
                Foreground = new Microsoft.UI.Xaml.Media.SolidColorBrush(Microsoft.UI.Colors.Salmon),
                TextWrapping = TextWrapping.Wrap,
            });
        }
    }

    private async Task RunHostedActionAsync(string endpoint, string tokenReference)
    {
        try
        {
            using var response = await _client.PostAsync(endpoint, new { token_id = tokenReference });
            await LoadPageAsync("hosted");
        }
        catch (Exception error)
        {
            PageContent.Children.Insert(0, new TextBlock
            {
                Text = error.Message,
                Foreground = new Microsoft.UI.Xaml.Media.SolidColorBrush(Microsoft.UI.Colors.Salmon),
                TextWrapping = TextWrapping.Wrap,
            });
        }
    }

    private static Grid CreateMetricGrid(params (string Label, string Value)[] metrics)
    {
        var grid = new Grid { ColumnSpacing = 12 };
        for (var index = 0; index < metrics.Length; index++)
        {
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            var card = new Border
            {
                Background = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaSurfaceBrush"],
                BorderBrush = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaBorderBrush"],
                BorderThickness = new Thickness(1),
                CornerRadius = new CornerRadius(8),
                Padding = new Thickness(16),
                Child = new StackPanel
                {
                    Spacing = 8,
                    Children =
                    {
                        new TextBlock { Text = metrics[index].Label, FontSize = 11, Foreground = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaMutedBrush"] },
                        new TextBlock { Text = metrics[index].Value, FontSize = 20, FontWeight = Microsoft.UI.Text.FontWeights.SemiBold, TextTrimming = TextTrimming.CharacterEllipsis },
                    },
                },
            };
            Grid.SetColumn(card, index);
            grid.Children.Add(card);
        }
        return grid;
    }

    private static Border CreateCard(string title, IEnumerable<(string Label, string Value)> values)
    {
        var content = new StackPanel { Spacing = 9 };
        content.Children.Add(new TextBlock { Text = title, FontSize = 15, FontWeight = Microsoft.UI.Text.FontWeights.SemiBold });
        foreach (var (label, value) in values)
        {
            var row = new Grid();
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(150) });
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            row.Children.Add(new TextBlock { Text = label, Foreground = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaMutedBrush"] });
            var valueText = new TextBlock { Text = value, TextWrapping = TextWrapping.Wrap };
            Grid.SetColumn(valueText, 1);
            row.Children.Add(valueText);
            content.Children.Add(row);
        }
        return CreatePanel(title, content);
    }

    private static Border CreatePanel(string title, UIElement child)
    {
        var content = new StackPanel { Spacing = 12 };
        content.Children.Add(new TextBlock { Text = title, FontSize = 15, FontWeight = Microsoft.UI.Text.FontWeights.SemiBold });
        content.Children.Add(child);
        return new Border
        {
            Background = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaSurfaceBrush"],
            BorderBrush = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaBorderBrush"],
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(8),
            Padding = new Thickness(16),
            Child = content,
        };
    }

    private static string ReadText(JsonElement element, string name, string fallback) =>
        element.TryGetProperty(name, out var value)
            ? value.ValueKind == JsonValueKind.String ? value.GetString() ?? fallback : value.ToString()
            : fallback;

    private static bool ReadBoolean(JsonElement element, string name) =>
        element.TryGetProperty(name, out var value) && value.ValueKind == JsonValueKind.True;
}
