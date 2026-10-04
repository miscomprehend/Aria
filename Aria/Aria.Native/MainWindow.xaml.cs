using System.Text.Json;
using System.Diagnostics;
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
        SidebarBrandIcon.Source = brandIcon;
        SetupBrandIcon.Source = brandIcon;
        ExtendsContentIntoTitleBar = true;
        SetTitleBar(TitleBar);
        var windowHandle = WinRT.Interop.WindowNative.GetWindowHandle(this);
        var windowId = Win32Interop.GetWindowIdFromWindow(windowHandle);
        var appWindow = AppWindow.GetFromWindowId(windowId);
        var nativeTitleBar = appWindow.TitleBar;
        nativeTitleBar.PreferredHeightOption = TitleBarHeightOption.Standard;
        nativeTitleBar.ButtonBackgroundColor = Microsoft.UI.Colors.Transparent;
        nativeTitleBar.ButtonInactiveBackgroundColor = Microsoft.UI.Colors.Transparent;
        nativeTitleBar.ButtonForegroundColor = Microsoft.UI.Colors.White;
        nativeTitleBar.ButtonInactiveForegroundColor = Microsoft.UI.ColorHelper.FromArgb(255, 164, 177, 191);
        nativeTitleBar.ButtonHoverBackgroundColor = Microsoft.UI.ColorHelper.FromArgb(255, 36, 51, 69);
        nativeTitleBar.ButtonPressedBackgroundColor = Microsoft.UI.ColorHelper.FromArgb(255, 45, 65, 87);
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
                SetSessionState("SETUP REQUIRED", 224, 180, 102);
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
                SetSessionState("SIGN IN REQUIRED", 224, 180, 102);
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
            SetSessionState("CONNECTION ISSUE", 255, 126, 135);
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
        RefreshButton.IsEnabled = false;
        PageStatus.Text = "● LOADING";
        PageStatus.Foreground = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaAccentBrush"];
        foreach (var button in Navigation.Children.OfType<Button>())
        {
            var isSelected = string.Equals(button.Tag?.ToString(), page, StringComparison.Ordinal);
            var foreground = isSelected
                ? (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaAccentBrush"]
                : new Microsoft.UI.Xaml.Media.SolidColorBrush(Microsoft.UI.ColorHelper.FromArgb(255, 190, 201, 212));
            button.Background = isSelected
                ? (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaNavActiveBrush"]
                : new Microsoft.UI.Xaml.Media.SolidColorBrush(Microsoft.UI.Colors.Transparent);
            button.BorderBrush = isSelected
                ? (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaAccentBrush"]
                : new Microsoft.UI.Xaml.Media.SolidColorBrush(Microsoft.UI.Colors.Transparent);
            button.BorderThickness = isSelected ? new Thickness(3, 0, 0, 0) : new Thickness(1);
            button.Foreground = foreground;
            if (button.Content is StackPanel content)
            {
                foreach (var element in content.Children)
                {
                    if (element is FontIcon icon)
                        icon.Foreground = foreground;
                    else if (element is TextBlock label)
                        label.Foreground = foreground;
                }
            }
        }

        try
        {
            switch (page)
            {
                case "hosted":
                    SetPageHeading("Hosted instances", "Manage the Aria clients attached to your account");
                    await LoadHostedAsync();
                    break;
                case "owner":
                    SetPageHeading("Owner tools", "Account access and recovery controls");
                    await LoadOwnerToolsAsync();
                    break;
                case "profile":
                    SetPageHeading("Profile & status", "Your connected account and client identity");
                    await LoadProfileAsync();
                    break;
                case "friends":
                    SetPageHeading("Friends", "Friend list and account visibility");
                    await LoadFriendsAsync();
                    break;
                case "presence":
                    SetPageHeading("Status", "Set the account’s online presence and client");
                    await LoadPresenceAsync();
                    break;
                case "access":
                    SetPageHeading("Access", "Hosted account access and registration");
                    await LoadAccessAsync();
                    break;
                case "rpc":
                    SetPageHeading("Presence studio", "Compose and control your Discord activity");
                    await LoadRpcAsync();
                    break;
                case "commands":
                    SetPageHeading("Commands", "Available commands for the active account");
                    await LoadCommandsAsync();
                    break;
                case "history":
                    SetPageHeading("Activity feed", "Recent command activity from the runtime");
                    await LoadHistoryAsync();
                    break;
                case "analytics":
                    SetPageHeading("Analytics", "Usage, performance, and command trends");
                    await LoadObjectPageAsync("/api/analytics", "data", "Performance overview");
                    break;
                case "boost":
                    SetPageHeading("Nitro", "Boost activity and available slots");
                    await LoadObjectPageAsync("/api/boost", "data", "Boost overview");
                    break;
                case "logger":
                    SetPageHeading("Message logger", "Configure and inspect the local message event feed");
                    await LoadMessageLoggerAsync();
                    break;
                case "automation":
                    SetPageHeading("Command controls", "Manage anti-GC and friend auto-reply tools");
                    await LoadAutomationAsync();
                    break;
                case "logs":
                    SetPageHeading("Runtime logs", "Recent diagnostics from the local Aria process");
                    await LoadCollectionPageAsync("/api/logs?lines=150", "lines", null);
                    break;
                case "settings":
                    SetPageHeading("Settings", "Configure the active account and command defaults");
                    await LoadSettingsAsync();
                    break;
                default:
                    SetPageHeading("Overview", "Your Aria runtime at a glance");
                    await LoadOverviewAsync();
                    break;
            }

            PageStatus.Text = "● READY";
            PageStatus.Foreground = new Microsoft.UI.Xaml.Media.SolidColorBrush(Microsoft.UI.Colors.LightGreen);
        }
        catch (Exception error)
        {
            PageStatus.Text = "● ERROR";
            PageStatus.Foreground = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaDangerBrush"];
            ShowPageError(error.Message);
        }
        finally
        {
            RefreshButton.IsEnabled = true;
        }
    }

    private void SetPageHeading(string title, string subtitle)
    {
        PageTitle.Text = title;
        PageSubtitle.Text = subtitle;
    }

    private void ShowPageError(string message)
    {
        PageContent.Children.Insert(0, new Border
        {
            Background = new Microsoft.UI.Xaml.Media.SolidColorBrush(Microsoft.UI.ColorHelper.FromArgb(36, 255, 126, 135)),
            BorderBrush = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaDangerBrush"],
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(8),
            Padding = new Thickness(14),
            Child = new TextBlock
            {
                Text = message,
                TextWrapping = TextWrapping.Wrap,
                Foreground = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaDangerBrush"],
            },
        });
    }

    private void BrowserDashboard_Click(object sender, RoutedEventArgs e) =>
        OpenExternalUrl(new Uri(new Uri(_baseUrl), "dashboard").ToString());

    private void Website_Click(object sender, RoutedEventArgs e) =>
        OpenExternalUrl(new Uri(_baseUrl).GetLeftPart(UriPartial.Authority) + "/");

    private void OpenExternalUrl(string url)
    {
        try
        {
            Process.Start(new ProcessStartInfo(url) { UseShellExecute = true });
        }
        catch (Exception error)
        {
            ShowPageError($"Could not open the browser: {error.Message}");
        }
    }

    private async Task LoadProfileAsync()
    {
        using var profileResult = await _client.GetAsync("/api/dash/me");
        using var botResult = await _client.GetAsync("/api/bot");
        var profile = profileResult.RootElement.GetProperty("profile");
        var bot = botResult.RootElement.GetProperty("data");
        PageContent.Children.Add(CreateMetricGrid(
            ("Role", ReadText(profile, "role", "user")),
            ("Discord account", ReadText(bot, "username", "Not connected")),
            ("Account ID", ReadText(profile, "user_id", "—"))));
        PageContent.Children.Add(CreateJsonPanel("Dashboard profile", profile));
        PageContent.Children.Add(CreateJsonPanel("Connected Aria account", bot));
    }

    private async Task LoadPresenceAsync()
    {
        using var presenceResult = await _client.GetAsync("/api/presence");
        using var clientResult = await _client.GetAsync("/api/client");
        using var afkResult = await _client.GetAsync("/api/afk");

        var status = new ComboBox { Header = "Online status", Width = 260 };
        var statuses = new[] { "online", "idle", "dnd", "invisible" };
        foreach (var value in statuses)
            status.Items.Add(value);
        var currentStatus = ReadText(presenceResult.RootElement, "status", "online");
        status.SelectedItem = statuses.Contains(currentStatus, StringComparer.OrdinalIgnoreCase)
            ? currentStatus
            : "online";
        var saveStatus = new Button { Content = "Update status", HorizontalAlignment = HorizontalAlignment.Left };
        saveStatus.Click += async (_, _) => await PostAndReloadAsync("/api/presence", new { status = status.SelectedItem?.ToString() ?? "online" });

        var clientType = new ComboBox { Header = "Client appearance", Width = 260 };
        var clients = clientResult.RootElement.GetProperty("available_clients");
        foreach (var item in clients.EnumerateArray())
            clientType.Items.Add(item.GetString() ?? "");
        var currentClient = ReadText(clientResult.RootElement, "client_type", "mobile");
        clientType.SelectedItem = currentClient;
        var saveClient = new Button { Content = "Update client", HorizontalAlignment = HorizontalAlignment.Left };
        saveClient.Click += async (_, _) => await PostAndReloadAsync("/api/client", new
        {
            client_type = clientType.SelectedItem?.ToString() ?? currentClient,
        });

        var afk = afkResult.RootElement;
        var afkMessage = new TextBox { Header = "AFK message", Text = ReadText(afk, "message", "AFK") };
        var afkActive = ReadBoolean(afk, "active");
        var afkToggle = new Button { Content = afkActive ? "Clear AFK" : "Set AFK" };
        afkToggle.Click += async (_, _) => await PostAndReloadAsync("/api/afk", new
        {
            action = afkActive ? "disable" : "enable",
            message = afkMessage.Text.Trim(),
        });

        PageContent.Children.Add(CreatePanel("Presence status", new StackPanel
        {
            Spacing = 10,
            Children = { status, saveStatus },
        }));
        PageContent.Children.Add(CreatePanel("Client appearance", new StackPanel
        {
            Spacing = 10,
            Children = { clientType, saveClient },
        }));
        PageContent.Children.Add(CreatePanel($"AFK mode · {(afkActive ? "active" : "inactive")}", new StackPanel
        {
            Spacing = 10,
            Children = { afkMessage, afkToggle },
        }));
    }

    private async Task LoadFriendsAsync()
    {
        using var result = await _client.GetAsync("/api/friends");
        var friends = result.RootElement.GetProperty("friends");
        PageContent.Children.Add(CreateMetricGrid(("Friends", ReadText(result.RootElement, "total", friends.GetArrayLength().ToString()))));
        AddCollectionCards(friends, "Friend", item =>
        {
            var name = ReadText(item, "username", "Unknown");
            var id = ReadText(item, "user_id", "");
            return CreateCard(name, new[]
            {
                ("User ID", id),
                ("Bot", ReadBoolean(item, "bot") ? "Yes" : "No"),
            });
        });
    }

    private async Task LoadAccessAsync()
    {
        using var result = await _client.GetAsync("/api/self-hosted");
        var root = result.RootElement;
        var accounts = root.GetProperty("accounts");
        PageContent.Children.Add(CreateMetricGrid(
            ("Hosted accounts", ReadText(root, "total", accounts.GetArrayLength().ToString())),
            ("Registration", ReadBoolean(root, "registration_enabled") ? "Open" : "Restricted"),
            ("Access", ReadBoolean(root, "is_owner") ? "Owner" : "Account owner")));

        var registerToken = new PasswordBox { Header = "Discord token", PasswordRevealMode = PasswordRevealMode.Peek };
        var prefix = new TextBox { Header = "Command prefix", Text = ";", Width = 130 };
        var register = new Button { Content = "Register account", HorizontalAlignment = HorizontalAlignment.Left };
        register.Click += async (_, _) =>
        {
            register.IsEnabled = false;
            try
            {
                using var response = await _client.PostAsync("/api/self-hosted", new
                {
                    action = "register",
                    token = registerToken.Password,
                    prefix = prefix.Text,
                });
                registerToken.Password = "";
                await LoadPageAsync("access");
            }
            catch (Exception error)
            {
                ShowPageError(error.Message);
                register.IsEnabled = true;
            }
        };
        if (ReadBoolean(root, "registration_enabled") || ReadBoolean(root, "is_owner"))
        {
            PageContent.Children.Add(CreatePanel("Register hosted account", new StackPanel
            {
                Spacing = 10,
                Children = { registerToken, prefix, register },
            }));
        }

        if (accounts.GetArrayLength() == 0)
        {
            PageContent.Children.Add(CreatePanel("Hosted accounts", new TextBlock
            {
                Text = "No hosted accounts are registered yet.",
                Foreground = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaMutedBrush"],
            }));
        }
        else
        {
            var cards = new StackPanel { Spacing = 10 };
            foreach (var account in accounts.EnumerateArray().Take(50))
            {
                var userId = ReadText(account, "user_id", "");
                var enabled = ReadBoolean(account, "enabled");
                var status = new TextBlock
                {
                    Text = enabled ? "Enabled" : "Disabled",
                    Foreground = enabled
                        ? new Microsoft.UI.Xaml.Media.SolidColorBrush(Microsoft.UI.Colors.LightGreen)
                        : (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaMutedBrush"],
                };
                var action = new Button { Content = enabled ? "Disable" : "Enable" };
                action.Click += async (_, _) =>
                {
                    try
                    {
                        using var response = await _client.PostAsync("/api/self-hosted", new
                        {
                            action = enabled ? "disable" : "enable",
                            user_id = userId,
                        });
                        await LoadPageAsync("access");
                    }
                    catch (Exception error)
                    {
                        ShowPageError(error.Message);
                    }
                };
                var content = new StackPanel { Spacing = 8 };
                content.Children.Add(CreateJsonDetails(account));
                content.Children.Add(status);
                content.Children.Add(action);
                cards.Children.Add(CreatePanel(ReadText(account, "username", "Hosted account"), content));
            }
            PageContent.Children.Add(CreatePanel("Hosted accounts", cards));
        }

        if (root.TryGetProperty("authorized_users", out var authorized) && authorized.ValueKind == JsonValueKind.Array)
            AddCollectionCards(authorized, "Authorized user", item => CreateJsonPanel("Authorized user", item));
    }

    private async Task LoadRpcAsync()
    {
        using var result = await _client.GetAsync("/api/rpc");
        var activity = result.RootElement.TryGetProperty("activity", out var current)
            && current.ValueKind == JsonValueKind.Object
            ? current
            : default;
        PageContent.Children.Add(CreateJsonPanel("Current activity", activity));

        var type = new ComboBox { Header = "Activity type", Width = 220 };
        type.Items.Add("Playing");
        type.Items.Add("Streaming");
        type.Items.Add("Listening");
        type.Items.Add("Watching");
        type.Items.Add("Competing");
        var activityType = ReadInteger(activity, "type", 0);
        type.SelectedIndex = activityType switch
        {
            1 => 1,
            2 => 2,
            3 => 3,
            5 => 4,
            _ => 0,
        };
        var activityTypes = new[] { 0, 1, 2, 3, 5 };
        var name = new TextBox { Header = "Activity name", Text = ReadText(activity, "name", "") };
        var details = new TextBox { Header = "Details", Text = ReadText(activity, "details", "") };
        var state = new TextBox { Header = "State", Text = ReadText(activity, "state", "") };
        var controls = new StackPanel { Spacing = 10 };
        controls.Children.Add(type);
        controls.Children.Add(name);
        controls.Children.Add(details);
        controls.Children.Add(state);
        var actions = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8 };
        var apply = new Button { Content = "Apply activity" };
        apply.Click += async (_, _) =>
        {
            if (string.IsNullOrWhiteSpace(name.Text))
            {
                ShowPageError("Enter an activity name before applying it.");
                return;
            }
            await PostAndReloadAsync("/api/rpc", new
            {
                action = "set",
                activity = new
                {
                    type = activityTypes[Math.Max(type.SelectedIndex, 0)],
                    name = name.Text.Trim(),
                    details = details.Text.Trim(),
                    state = state.Text.Trim(),
                },
            });
        };
        var stop = new Button { Content = "Stop activity" };
        stop.Click += async (_, _) => await PostAndReloadAsync("/api/rpc", new { action = "stop" });
        actions.Children.Add(apply);
        actions.Children.Add(stop);
        controls.Children.Add(actions);
        PageContent.Children.Add(CreatePanel("Activity composer", controls));
    }

    private async Task LoadMessageLoggerAsync()
    {
        using var result = await _client.GetAsync("/api/message-logger");
        var config = result.RootElement.GetProperty("config");
        var enabled = new CheckBox { Content = "Enable message event logging", IsChecked = ReadBoolean(config, "enabled") };
        var mentions = new CheckBox { Content = "Log mentions and keyword matches", IsChecked = ReadBoolean(config, "mentions") };
        var edits = new CheckBox { Content = "Log message edits", IsChecked = ReadBoolean(config, "edits") };
        var deletes = new CheckBox { Content = "Log message deletions", IsChecked = ReadBoolean(config, "deletes") };
        var ignoreSelf = new CheckBox { Content = "Ignore the active account", IsChecked = ReadBoolean(config, "ignore_self") };
        var save = new Button { Content = "Save logger settings", HorizontalAlignment = HorizontalAlignment.Left };
        save.Click += async (_, _) => await PostAndReloadAsync("/api/message-logger", new
        {
            action = "config",
            config = new
            {
                enabled = enabled.IsChecked == true,
                mentions = mentions.IsChecked == true,
                edits = edits.IsChecked == true,
                deletes = deletes.IsChecked == true,
                ignore_self = ignoreSelf.IsChecked == true,
            },
        });
        var settings = new StackPanel { Spacing = 6 };
        settings.Children.Add(enabled);
        settings.Children.Add(mentions);
        settings.Children.Add(edits);
        settings.Children.Add(deletes);
        settings.Children.Add(ignoreSelf);
        settings.Children.Add(save);
        PageContent.Children.Add(CreatePanel("Logger settings", settings));

        var feed = result.RootElement.GetProperty("feed");
        var feedPanel = new StackPanel { Spacing = 8 };
        var clear = new Button { Content = "Clear feed", HorizontalAlignment = HorizontalAlignment.Left };
        clear.Click += async (_, _) => await PostAndReloadAsync("/api/message-logger", new { action = "clear" });
        feedPanel.Children.Add(clear);
        foreach (var item in feed.EnumerateArray().Take(50))
            feedPanel.Children.Add(CreateJsonPanel(
                ReadText(item, "kind", "Message event"),
                item));
        if (feed.GetArrayLength() == 0)
            feedPanel.Children.Add(new TextBlock
            {
                Text = "No message events have been recorded.",
                Foreground = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaMutedBrush"],
            });
        PageContent.Children.Add(CreatePanel($"Recent events ({feed.GetArrayLength()})", feedPanel));
    }

    private async Task LoadAutomationAsync()
    {
        using var result = await _client.GetAsync("/api/command-tools");
        var antiGc = result.RootElement.GetProperty("anti_gc");
        var enabled = new CheckBox { Content = "Enable anti-group-chat trap", IsChecked = ReadBoolean(antiGc, "enabled") };
        var creators = new CheckBox { Content = "Block group-chat creators", IsChecked = ReadBoolean(antiGc, "block_creators") };
        var save = new Button { Content = "Save controls", HorizontalAlignment = HorizontalAlignment.Left };
        save.Click += async (_, _) =>
        {
            save.IsEnabled = false;
            try
            {
                using var enabledResult = await _client.PostAsync("/api/command-tools", new
                {
                    action = "antigc_enabled",
                    value = enabled.IsChecked == true,
                });
                using var creatorsResult = await _client.PostAsync("/api/command-tools", new
                {
                    action = "antigc_block_creators",
                    value = creators.IsChecked == true,
                });
                await LoadPageAsync("automation");
            }
            catch (Exception error)
            {
                ShowPageError(error.Message);
                save.IsEnabled = true;
            }
        };
        PageContent.Children.Add(CreatePanel("Anti-GC protection", new StackPanel
        {
            Spacing = 8,
            Children = { enabled, creators, save },
        }));
        if (result.RootElement.TryGetProperty("auto_replies", out var replies))
            AddCollectionCards(replies, "Auto-reply", item => CreateJsonPanel("Auto-reply target", item));
    }

    private async Task LoadSettingsAsync()
    {
        using var result = await _client.GetAsync("/api/config");
        var data = result.RootElement.GetProperty("data");
        var prefix = new TextBox { Header = "Command prefix", Text = ReadText(data, "prefix", ";"), Width = 180 };
        var autoDelete = new CheckBox
        {
            Content = "Automatically delete command responses",
            IsChecked = ReadBoolean(data, "auto_delete_enabled"),
        };
        var deleteDelay = new NumberBox
        {
            Header = "Auto-delete delay (seconds)",
            Value = ReadDouble(data, "auto_delete_delay", 10),
            Minimum = 1,
            Maximum = 600,
            Width = 240,
        };
        var save = new Button { Content = "Save settings", HorizontalAlignment = HorizontalAlignment.Left };
        save.Click += async (_, _) => await PostAndReloadAsync("/api/config", new
        {
            prefix = prefix.Text.Trim(),
            auto_delete_enabled = autoDelete.IsChecked == true,
            auto_delete_delay = (int)deleteDelay.Value,
        });
        var form = new StackPanel { Spacing = 10 };
        form.Children.Add(prefix);
        form.Children.Add(autoDelete);
        form.Children.Add(deleteDelay);
        form.Children.Add(save);
        PageContent.Children.Add(CreatePanel("Account settings", form));
        PageContent.Children.Add(CreateJsonPanel("Current configuration", data));
    }

    private async Task LoadObjectPageAsync(string endpoint, string property, string panelTitle)
    {
        using var result = await _client.GetAsync(endpoint);
        var data = result.RootElement.GetProperty(property);
        PageContent.Children.Add(CreateJsonPanel(panelTitle, data));
    }

    private async Task LoadCommandsAsync()
    {
        using var result = await _client.GetAsync("/api/commands");
        var data = result.RootElement.GetProperty("data");
        var commands = data.GetProperty("commands");
        PageContent.Children.Add(CreateMetricGrid(
            ("Commands", ReadText(data, "total", commands.GetArrayLength().ToString())),
            ("Prefix", ReadText(data, "prefix", "—"))));

        var cards = new StackPanel { Spacing = 10 };
        foreach (var command in commands.EnumerateArray().Take(150))
        {
            var name = ReadText(command, "name", "command");
            var header = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8 };
            header.Children.Add(new TextBlock
            {
                Text = ReadText(data, "prefix", "") + name,
                FontSize = 15,
                FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
                VerticalAlignment = VerticalAlignment.Center,
            });
            header.Children.Add(CreateBadge(
                $"{ReadText(command, "recent_usage", "0")} recent uses",
                Microsoft.UI.ColorHelper.FromArgb(255, 28, 49, 69)));

            var content = new StackPanel { Spacing = 8 };
            content.Children.Add(header);
            var description = ReadText(command, "description", "");
            if (!string.IsNullOrWhiteSpace(description))
                content.Children.Add(new TextBlock
                {
                    Text = description,
                    TextWrapping = TextWrapping.Wrap,
                    Foreground = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaMutedBrush"],
                });
            if (command.TryGetProperty("aliases", out var aliases)
                && aliases.ValueKind == JsonValueKind.Array
                && aliases.GetArrayLength() > 0)
            {
                var aliasRow = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 6 };
                aliasRow.Children.Add(new TextBlock
                {
                    Text = "ALIASES",
                    FontSize = 9,
                    Foreground = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaMutedBrush"],
                    VerticalAlignment = VerticalAlignment.Center,
                });
                foreach (var alias in aliases.EnumerateArray().Take(8))
                    aliasRow.Children.Add(CreateBadge(alias.ToString(), Microsoft.UI.ColorHelper.FromArgb(255, 21, 31, 43)));
                content.Children.Add(aliasRow);
            }
            cards.Children.Add(CreatePanel(name, content));
        }
        if (commands.GetArrayLength() == 0)
            cards.Children.Add(new TextBlock
            {
                Text = ReadText(data, "error", "No commands are available."),
                TextWrapping = TextWrapping.Wrap,
                Foreground = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaMutedBrush"],
            });
        PageContent.Children.Add(CreatePanel("Command catalog", cards));
    }

    private async Task LoadHistoryAsync()
    {
        using var result = await _client.GetAsync("/api/history");
        var data = result.RootElement.GetProperty("data");
        var entries = data.GetProperty("entries");
        var total = entries.GetArrayLength();
        var failures = entries.EnumerateArray().Count(item =>
            string.Equals(ReadText(item, "status", "success"), "failed", StringComparison.OrdinalIgnoreCase));
        PageContent.Children.Add(CreateMetricGrid(
            ("Recorded commands", ReadText(data, "total", total.ToString())),
            ("Successful", Math.Max(0, total - failures).ToString()),
            ("Failed", failures.ToString())));

        var rows = new StackPanel { Spacing = 8 };
        foreach (var entry in entries.EnumerateArray().Take(50))
        {
            var command = ReadText(entry, "command", ReadText(entry, "cmd", "Command"));
            var status = ReadText(entry, "status", "success");
            var header = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8 };
            header.Children.Add(new TextBlock
            {
                Text = command,
                FontSize = 14,
                FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
                VerticalAlignment = VerticalAlignment.Center,
            });
            header.Children.Add(CreateBadge(
                status.ToUpperInvariant(),
                string.Equals(status, "failed", StringComparison.OrdinalIgnoreCase)
                    ? Microsoft.UI.ColorHelper.FromArgb(255, 73, 35, 43)
                    : Microsoft.UI.ColorHelper.FromArgb(255, 27, 61, 52)));
            header.Children.Add(CreateBadge(
                $"{ReadText(entry, "duration_ms", "—")} ms",
                Microsoft.UI.ColorHelper.FromArgb(255, 21, 31, 43)));
            var detail = new TextBlock
            {
                Text = $"{ReadText(entry, "timestamp", "Time unavailable")}  ·  {ReadText(entry, "user", "Unknown user")}  ·  {ReadText(entry, "guild", "Direct message")}",
                TextWrapping = TextWrapping.Wrap,
                Foreground = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaMutedBrush"],
                FontSize = 11,
            };
            rows.Children.Add(CreatePanel(command, new StackPanel { Spacing = 7, Children = { header, detail } }));
        }
        if (total == 0)
            rows.Children.Add(new TextBlock
            {
                Text = "No command activity has been recorded yet.",
                Foreground = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaMutedBrush"],
            });
        else if (total > 50)
            rows.Children.Add(new TextBlock
            {
                Text = $"Showing the latest 50 of {total} entries.",
                Foreground = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaMutedBrush"],
            });
        PageContent.Children.Add(CreatePanel("Recent activity", rows));
    }

    private static Border CreateBadge(string text, Windows.UI.Color color) => new()
    {
        Background = new Microsoft.UI.Xaml.Media.SolidColorBrush(color),
        BorderBrush = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaBorderBrush"],
        BorderThickness = new Thickness(1),
        CornerRadius = new CornerRadius(10),
        Padding = new Thickness(8, 3, 8, 3),
        Child = new TextBlock
        {
            Text = text,
            FontSize = 10,
            VerticalAlignment = VerticalAlignment.Center,
        },
    };

    private async Task LoadCollectionPageAsync(string endpoint, string rootProperty, string? nestedProperty)
    {
        using var result = await _client.GetAsync(endpoint);
        var collection = result.RootElement.GetProperty(rootProperty);
        if (nestedProperty is not null)
        {
            if (collection.ValueKind != JsonValueKind.Object || !collection.TryGetProperty(nestedProperty, out collection))
                throw new InvalidOperationException($"Aria did not return the expected {nestedProperty} list.");
        }
        if (collection.ValueKind != JsonValueKind.Array)
            throw new InvalidOperationException($"Aria returned an invalid {rootProperty} list.");

        var count = ReadText(result.RootElement, "total", collection.GetArrayLength().ToString());
        PageContent.Children.Add(CreateMetricGrid(("Items", count)));
        var shown = 0;
        foreach (var item in collection.EnumerateArray().Take(150))
        {
            shown++;
            if (item.ValueKind == JsonValueKind.Object)
                PageContent.Children.Add(CreateJsonPanel(
                    ReadText(item, "command", ReadText(item, "name", $"Item {shown}")),
                    item));
            else
                PageContent.Children.Add(CreatePanel(
                    $"Entry {shown}",
                    new TextBlock { Text = item.ToString(), TextWrapping = TextWrapping.Wrap }));
        }
        if (shown == 0)
            PageContent.Children.Add(CreatePanel("Nothing to show", new TextBlock
            {
                Text = "No items are available yet.",
                Foreground = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaMutedBrush"],
            }));
        else if (collection.GetArrayLength() > shown)
            PageContent.Children.Add(new TextBlock
            {
                Text = $"Showing {shown} of {collection.GetArrayLength()} items. Open the browser panel for the complete list.",
                Foreground = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaMutedBrush"],
                TextWrapping = TextWrapping.Wrap,
            });
    }

    private void AddCollectionCards(
        JsonElement collection,
        string emptyTitle,
        Func<JsonElement, UIElement> createItem)
    {
        if (collection.ValueKind != JsonValueKind.Array)
            throw new InvalidOperationException("Aria returned an invalid list.");
        if (collection.GetArrayLength() == 0)
        {
            PageContent.Children.Add(CreatePanel(emptyTitle, new TextBlock
            {
                Text = "Nothing to show yet.",
                Foreground = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaMutedBrush"],
            }));
            return;
        }
        var list = new StackPanel { Spacing = 10 };
        foreach (var item in collection.EnumerateArray().Take(100))
            list.Children.Add(createItem(item));
        PageContent.Children.Add(CreatePanel($"{emptyTitle} list ({collection.GetArrayLength()})", list));
    }

    private async Task PostAndReloadAsync(string path, object payload)
    {
        try
        {
            using var result = await _client.PostAsync(path, payload);
            await LoadPageAsync(_page);
        }
        catch (Exception error)
        {
            ShowPageError(error.Message);
        }
    }

    private async Task LoadIdentityAsync()
    {
        using var response = await _client.GetAsync("/api/dash/me");
        var profile = response.RootElement.GetProperty("profile");
        SessionIdentity.Text = ReadText(profile, "username", "Signed in");
        SetSessionState("SIGNED IN", 103, 214, 160);
        OwnerNavigationButton.Visibility = ReadBoolean(profile, "is_owner")
            ? Visibility.Visible
            : Visibility.Collapsed;
    }

    private void SetSessionState(string status, byte red, byte green, byte blue)
    {
        var brush = new Microsoft.UI.Xaml.Media.SolidColorBrush(
            Microsoft.UI.ColorHelper.FromArgb(255, red, green, blue));
        SessionStatusText.Text = status;
        SessionStatusText.Foreground = brush;
        SessionStatusDot.Fill = brush;
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

        var ownerAccounts = new StackPanel { Spacing = 10 };
        foreach (var owner in data.GetProperty("master_owners").EnumerateArray())
        {
            var ownerId = ReadText(owner, "user_id", "");
            var ownerName = ReadText(owner, "username", "Owner");
            var details = new StackPanel { Spacing = 4 };
            details.Children.Add(new TextBlock
            {
                Text = ownerName,
                FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            });
            details.Children.Add(new TextBlock
            {
                Text = $"Account ID: {ownerId}",
                IsTextSelectionEnabled = true,
                Foreground = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaMutedBrush"],
                TextWrapping = TextWrapping.Wrap,
            });
            var reset = new Button { Content = "Reset password" };
            reset.Click += async (_, _) => await ResetOwnerPasswordAsync(ownerId, reset);
            var row = new StackPanel { Spacing = 8 };
            row.Children.Add(details);
            row.Children.Add(reset);
            ownerAccounts.Children.Add(new Border
            {
                Background = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaRaisedBrush"],
                BorderBrush = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaBorderBrush"],
                BorderThickness = new Thickness(1),
                CornerRadius = new CornerRadius(6),
                Padding = new Thickness(12),
                Child = row,
            });
        }
        PageContent.Children.Add(CreatePanel("Owner accounts", ownerAccounts));

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

    private async Task ResetOwnerPasswordAsync(string ownerId, Button button)
    {
        button.IsEnabled = false;
        try
        {
            using var response = await _client.PostAsync(
                $"/api/owner/accounts/{Uri.EscapeDataString(ownerId)}/password",
                new { });
            var username = ReadText(response.RootElement, "username", ownerId);
            var password = ReadText(response.RootElement, "password", "");
            if (password.Length == 0)
                throw new InvalidOperationException("The server did not return the one-time password.");

            var content = new StackPanel { Spacing = 8 };
            content.Children.Add(new TextBlock
            {
                Text = $"{username} ({ownerId})",
                TextWrapping = TextWrapping.Wrap,
            });
            content.Children.Add(new TextBlock
            {
                Text = password,
                IsTextSelectionEnabled = true,
                FontFamily = new Microsoft.UI.Xaml.Media.FontFamily("Consolas"),
                TextWrapping = TextWrapping.Wrap,
            });
            content.Children.Add(new TextBlock
            {
                Text = "Copy and store this password securely. Aria stores only its hash and will not show the password again.",
                TextWrapping = TextWrapping.Wrap,
                Foreground = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaMutedBrush"],
            });
            var dialog = new ContentDialog
            {
                Title = "New owner password",
                Content = content,
                CloseButtonText = "Done",
                XamlRoot = PageContent.XamlRoot,
            };
            await dialog.ShowAsync();
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
        finally
        {
            button.IsEnabled = true;
        }
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
                CornerRadius = new CornerRadius(11),
                Padding = new Thickness(18),
                Child = new Grid
                {
                    RowDefinitions =
                    {
                        new RowDefinition { Height = GridLength.Auto },
                        new RowDefinition { Height = GridLength.Auto },
                    },
                },
            };
            var metricContent = (Grid)card.Child;
            metricContent.RowSpacing = 9;
            metricContent.Children.Add(new Border
            {
                Width = 26,
                Height = 3,
                HorizontalAlignment = HorizontalAlignment.Left,
                Background = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaAccentBrush"],
                CornerRadius = new CornerRadius(2),
            });
            var metricValue = new StackPanel { Spacing = 5 };
            metricValue.Children.Add(new TextBlock
            {
                Text = metrics[index].Label,
                FontSize = 11,
                FontWeight = Microsoft.UI.Text.FontWeights.Medium,
                Foreground = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaMutedBrush"],
            });
            metricValue.Children.Add(new TextBlock
            {
                Text = metrics[index].Value,
                FontSize = 21,
                FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
                TextTrimming = TextTrimming.CharacterEllipsis,
            });
            Grid.SetRow(metricValue, 1);
            metricContent.Children.Add(metricValue);
            Grid.SetColumn(card, index);
            grid.Children.Add(card);
        }
        return grid;
    }

    private static Border CreateCard(string title, IEnumerable<(string Label, string Value)> values)
    {
        var content = new StackPanel { Spacing = 9 };
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
        var heading = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 10 };
        heading.Children.Add(new Border
        {
            Width = 3,
            Height = 17,
            CornerRadius = new CornerRadius(2),
            Background = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaAccentBrush"],
            VerticalAlignment = VerticalAlignment.Center,
        });
        heading.Children.Add(new TextBlock
        {
            Text = title,
            FontSize = 15,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            VerticalAlignment = VerticalAlignment.Center,
        });
        content.Children.Add(heading);
        content.Children.Add(child);
        return new Border
        {
            Background = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaSurfaceBrush"],
            BorderBrush = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaBorderBrush"],
            BorderThickness = new Thickness(1),
            CornerRadius = new CornerRadius(11),
            Padding = new Thickness(18),
            Child = content,
        };
    }

    private static Border CreateJsonPanel(string title, JsonElement data)
    {
        if (data.ValueKind == JsonValueKind.Undefined || data.ValueKind == JsonValueKind.Null)
            return CreatePanel(title, new TextBlock
            {
                Text = "No current data.",
                Foreground = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaMutedBrush"],
            });
        return CreatePanel(title, CreateJsonDetails(data));
    }

    private static StackPanel CreateJsonDetails(JsonElement data)
    {
        var details = new StackPanel { Spacing = 8 };
        if (data.ValueKind != JsonValueKind.Object)
        {
            details.Children.Add(new TextBlock
            {
                Text = DisplayJsonValue(data),
                TextWrapping = TextWrapping.Wrap,
                IsTextSelectionEnabled = true,
            });
            return details;
        }

        AppendJsonProperties(details, data, "", 0);
        if (!data.EnumerateObject().Any())
            details.Children.Add(new TextBlock
            {
                Text = "No data is available yet.",
                Foreground = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaMutedBrush"],
            });
        return details;
    }

    private static void AppendJsonProperties(StackPanel details, JsonElement data, string prefix, int depth)
    {
        foreach (var property in data.EnumerateObject().Take(24))
        {
            if (details.Children.Count >= 48)
                return;
            if (property.Value.ValueKind is JsonValueKind.Null or JsonValueKind.Undefined
                || IsSensitiveKey(property.Name))
                continue;

            var label = prefix + HumanizeKey(property.Name);
            if (property.Value.ValueKind == JsonValueKind.Object && depth < 2)
            {
                AppendJsonProperties(details, property.Value, label + " · ", depth + 1);
                continue;
            }

            var row = new Grid { ColumnSpacing = 14 };
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(170) });
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            row.Children.Add(new TextBlock
            {
                Text = label,
                Foreground = (Microsoft.UI.Xaml.Media.Brush)Application.Current.Resources["AriaMutedBrush"],
                TextWrapping = TextWrapping.Wrap,
            });
            var value = new TextBlock
            {
                Text = DisplayJsonValue(property.Value),
                TextWrapping = TextWrapping.Wrap,
                IsTextSelectionEnabled = true,
            };
            Grid.SetColumn(value, 1);
            row.Children.Add(value);
            details.Children.Add(row);
        }
    }

    private static string DisplayJsonValue(JsonElement value)
    {
        if (value.ValueKind == JsonValueKind.Array)
            return $"{value.GetArrayLength()} items";
        var text = value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? ""
            : value.ValueKind == JsonValueKind.Object
                ? "Object"
                : value.ToString();
        return text.Length > 500 ? text[..497] + "..." : text;
    }

    private static string HumanizeKey(string key)
    {
        var label = key.Replace('_', ' ');
        if (label.Length == 0)
            return label;
        return char.ToUpperInvariant(label[0]) + label[1..];
    }

    private static bool IsSensitiveKey(string key)
    {
        var normalized = key.Replace("_", "", StringComparison.Ordinal)
            .Replace("-", "", StringComparison.Ordinal)
            .ToLowerInvariant();
        return normalized is "token" or "discordtoken" or "authtoken" or "accesstoken"
            or "password" or "passwordhash" or "secret" or "clientsecret"
            or "cookie" or "authorization" or "apikey";
    }

    private static string ReadText(JsonElement element, string name, string fallback) =>
        element.ValueKind == JsonValueKind.Object && element.TryGetProperty(name, out var value)
            ? value.ValueKind == JsonValueKind.String ? value.GetString() ?? fallback : value.ToString()
            : fallback;

    private static bool ReadBoolean(JsonElement element, string name) =>
        element.ValueKind == JsonValueKind.Object
        && element.TryGetProperty(name, out var value)
        && value.ValueKind == JsonValueKind.True;

    private static int ReadInteger(JsonElement element, string name, int fallback) =>
        element.ValueKind == JsonValueKind.Object
        && element.TryGetProperty(name, out var value)
        && value.TryGetInt32(out var result)
            ? result
            : fallback;

    private static double ReadDouble(JsonElement element, string name, double fallback) =>
        element.ValueKind == JsonValueKind.Object
        && element.TryGetProperty(name, out var value)
        && value.TryGetDouble(out var result)
            ? result
            : fallback;
}
