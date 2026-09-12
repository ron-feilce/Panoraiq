import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.regex.Pattern;

/** A compiled, dependency-free HTTP contract check for the actual release image. */
public final class SmokeCheck {
    private static final Pattern HEALTHY = Pattern.compile("\"status\"\\s*:\\s*\"ok\"");

    public static void main(String[] args) throws Exception {
        if (args.length != 1) {
            throw new IllegalArgumentException("Usage: java SmokeCheck http://app:8000");
        }
        URI base = URI.create(args[0]);
        HttpClient client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build();
        HttpResponse<String> health = get(client, base.resolve("/healthz"));
        if (health.statusCode() != 200 || !HEALTHY.matcher(health.body()).find()) {
            throw new IllegalStateException("Database health check failed: HTTP " + health.statusCode());
        }
        HttpResponse<String> page = get(client, base.resolve("/"));
        if (page.statusCode() != 200 || !page.body().contains("Studio Ledger")
                || !page.body().contains("csrf_token") || !page.body().contains("Add a work")) {
            throw new IllegalStateException("Catalog page contract failed: HTTP " + page.statusCode());
        }
        System.out.println("PASS: Release image serves the catalog and reaches its database.");
    }

    private static HttpResponse<String> get(HttpClient client, URI uri) throws Exception {
        HttpRequest request = HttpRequest.newBuilder(uri).timeout(Duration.ofSeconds(10)).GET().build();
        return client.send(request, HttpResponse.BodyHandlers.ofString());
    }
}
