using System.Net;
using System.Net.Http.Json;
using System.Text.Json;

namespace Aria.Native;

internal sealed record NativeSetupResult(string DashboardUrl, string AuthToken);

internal sealed class NativeSetupClient
{
    private readonly HttpClient _http = new(new HttpClientHandler { UseProxy = false })
    {
        Timeout = TimeSpan.FromMinutes(2),
    };
    private readonly string _controlToken;

    public NativeSetupClient()
    {
        _controlToken = Environment.GetEnvironmentVariable("ARIA_NATIVE_CONTROL_TOKEN") ?? "";
    }

    public async Task<NativeSetupResult> SaveTokenAsync(string token, bool remember)
    {
        var controlUrl = Environment.GetEnvironmentVariable("ARIA_NATIVE_CONTROL_URL") ?? "";
        if (!Uri.TryCreate(controlUrl, UriKind.Absolute, out var uri)
            || uri.Scheme != Uri.UriSchemeHttp
            || !IPAddress.TryParse(uri.Host, out var address)
            || !IPAddress.IsLoopback(address))
            throw new InvalidOperationException("The secure local setup channel is unavailable. Restart Aria Desktop and try again.");
        if (string.IsNullOrWhiteSpace(_controlToken))
            throw new InvalidOperationException("The secure local setup channel has expired. Restart Aria Desktop and try again.");

        using var request = new HttpRequestMessage(HttpMethod.Post, uri)
        {
            Content = JsonContent.Create(new
            {
                action = "save-token",
                token,
                remember,
            }),
        };
        request.Headers.Authorization =
            new System.Net.Http.Headers.AuthenticationHeaderValue("Bearer", _controlToken);
        using var response = await _http.SendAsync(request);
        var body = await response.Content.ReadAsStringAsync();
        using var document = JsonDocument.Parse(body);
        var root = document.RootElement;
        if (!response.IsSuccessStatusCode
            || !root.TryGetProperty("ok", out var ok)
            || !ok.GetBoolean())
        {
            var error = root.TryGetProperty("error", out var errorElement)
                ? errorElement.GetString()
                : null;
            throw new InvalidOperationException(error ?? $"Token setup failed (HTTP {(int)response.StatusCode}).");
        }

        var dashboardUrl = root.GetProperty("dashboardUrl").GetString() ?? "";
        var authToken = root.GetProperty("authToken").GetString() ?? "";
        if (string.IsNullOrWhiteSpace(dashboardUrl) || string.IsNullOrWhiteSpace(authToken))
            throw new InvalidOperationException("Aria restarted, but did not return the local owner session.");
        return new NativeSetupResult(dashboardUrl, authToken);
    }
}
