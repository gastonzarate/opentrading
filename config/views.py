from django.views.generic import TemplateView


class HomePageView(TemplateView):
    template_name = "index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Same-origin (relative) API base. The dashboard and the REST API are
        # served by this same app, so a relative base ("") makes the browser use
        # the page's own origin+scheme. Building an absolute URL here broke access
        # through an HTTPS tunnel (Cloudflare/ngrok): TLS terminates at the proxy
        # and Django sees HTTP, so it emitted an http:// base that the HTTPS page
        # then couldn't fetch (mixed content) — the dashboard loaded but showed no
        # data. Relative avoids the scheme problem entirely.
        context["api_base_url"] = ""
        return context
