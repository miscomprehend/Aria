using System.Net;
using System.Net.Http.Json;
using System.Text.RegularExpressions;
using System.Text.Json;

namespace Aria.Native;

internal sealed class AriaDashboardClient
{
    private readonly HttpClient _http;
    private string _csrfToken = "";

    public AriaDashboardClient()
    {
        var handler = new HttpClientHandler
        {
            CookieContainer = new CookieContainer(),
            UseCookies = true,
            AllowAutoRedirect = false,
        };
        _http = new HttpClient(handler) { Timeout = TimeSpan.FromSeconds(20) };
    }

    public async Task AuthenticateOwnerAsync(string baseUrl, string oneTimeToken)
    {
        SetBaseAddress(baseUrl);

        using var response = await _http.PostAsJsonAsync(
            "__electron__/owner-session",
            new { token = oneTimeToken });
        using var result = await ReadJsonAsync(response);
        if (!result.RootElement.TryGetProperty("ok", out var ok) || !ok.GetBoolean())
            throw new InvalidOperationException(ReadError(result.RootElement, "Owner sign-in failed."));
        _csrfToken = result.RootElement.TryGetProperty("csrf_token", out var csrf)
            ? csrf.GetString() ?? ""
            : "";
        if (string.IsNullOrWhiteSpace(_csrfToken))
            throw new InvalidOperationException("The local dashboard did not provide a request-protection token.");
    }

    public void SetBaseAddress(string baseUrl)
    {
        if (!Uri.TryCreate(baseUrl, UriKind.Absolute, out var uri)
            || uri.Scheme != Uri.UriSchemeHttp
            || !IPAddress.TryParse(uri.Host, out var address)
            || !IPAddress.IsLoopback(address))
            throw new InvalidOperationException("The native dashboard only connects to the local Aria service.");

        _http.BaseAddress = new Uri(baseUrl.TrimEnd('/') + "/");
    }

    public async Task LoginAsync(string username, string password, string discordId)
    {
        using var loginPage = await _http.GetAsync("/login?next=%2Fdashboard");
        var loginHtml = await loginPage.Content.ReadAsStringAsync();
        var csrfMatch = Regex.Match(
            loginHtml,
            """name=['"]csrf_token['"][^>]*value=['"]([^'"]+)['"]""",
            RegexOptions.IgnoreCase);
        if (!csrfMatch.Success)
            throw new InvalidOperationException("Could not start a secure sign-in session.");

        using var form = new FormUrlEncodedContent(new Dictionary<string, string>
        {
            ["csrf_token"] = WebUtility.HtmlDecode(csrfMatch.Groups[1].Value),
            ["username"] = username,
            ["password"] = password,
            ["discord_id"] = discordId,
            ["next"] = "/dashboard",
        });
        using var response = await _http.PostAsync("/login", form);
        if ((int)response.StatusCode is < 300 or >= 400)
            throw new InvalidOperationException("The Aria sign-in request was rejected.");

        using var dashboard = await _http.GetAsync("/dashboard");
        var dashboardHtml = await dashboard.Content.ReadAsStringAsync();
        var tokenMatch = Regex.Match(
            dashboardHtml,
            """<meta\s+name=['"]csrf-token['"]\s+content=['"]([^'"]+)['"]""",
            RegexOptions.IgnoreCase);
        if (!dashboard.IsSuccessStatusCode || !tokenMatch.Success)
            throw new InvalidOperationException("Sign-in failed. Check your account credentials and Discord ID.");
        _csrfToken = WebUtility.HtmlDecode(tokenMatch.Groups[1].Value);
        if (string.IsNullOrWhiteSpace(_csrfToken))
            throw new InvalidOperationException("The local dashboard did not provide a request-protection token.");
    }

    public async Task<JsonDocument> GetAsync(string path)
    {
        using var response = await _http.GetAsync(path);
        return await ReadJsonAsync(response);
    }

    public async Task<JsonDocument> PostAsync(string path, object payload)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, path)
        {
            Content = JsonContent.Create(payload),
        };
        request.Headers.TryAddWithoutValidation("X-CSRF-Token", _csrfToken);
        using var response = await _http.SendAsync(request);
        return await ReadJsonAsync(response);
    }

    private static async Task<JsonDocument> ReadJsonAsync(HttpResponseMessage response)
    {
        var body = await response.Content.ReadAsStringAsync();
        JsonDocument? document = null;
        try
        {
            document = JsonDocument.Parse(body);
            if (!response.IsSuccessStatusCode)
                throw new InvalidOperationException(ReadError(document.RootElement, $"Aria returned HTTP {(int)response.StatusCode}."));
            if (document.RootElement.TryGetProperty("ok", out var ok) && ok.ValueKind == JsonValueKind.False)
                throw new InvalidOperationException(ReadError(document.RootElement, "The Aria request failed."));
            return document;
        }
        catch (JsonException)
        {
            throw new InvalidOperationException($"Aria returned an unexpected response (HTTP {(int)response.StatusCode}).");
        }
        catch
        {
            document?.Dispose();
            throw;
        }
    }

    private static string ReadError(JsonElement element, string fallback) =>
        element.TryGetProperty("error", out var error) && error.ValueKind == JsonValueKind.String
            ? error.GetString() ?? fallback
            : fallback;
}
