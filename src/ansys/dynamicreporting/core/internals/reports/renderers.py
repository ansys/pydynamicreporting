from ceireports.utils import get_render_error_html
from rest_framework.exceptions import APIException
from rest_framework.renderers import BaseRenderer, TemplateHTMLRenderer as BaseHTMLRenderer

from .engine import TemplateEngine


class ReportRenderer(BaseRenderer):
    """
    Base report renderer.

    If writing a report render, few class variables
    may need to be overridden:
    - media_type = None # is the content type to send
    to the browser.
    Ref: https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types/Common_types
    - format = None # makes DRF catch the query_param
    'format' and tells the response to use this renderer.
    - charset = 'utf-8' # character set
    - render_style = 'text' # render style - text/binary
    """

    def render(self, response_data, accepted_media_type=None, renderer_context=None):
        ctx = response_data["ctx"]
        engine = response_data["engine"]
        items = response_data["items"]
        try:
            # returns bytes or string depending on the engine renderer
            content = engine.dispatch_render(self.format, items, ctx)
        except Exception as e:
            # exceptions must be handled in the child classes, returning
            # the appropriate type of response
            raise Exception(f"Unable to render report: {e}")
        return content


class StaticHTMLReportRenderer(ReportRenderer, BaseHTMLRenderer):
    """
    This is targeted towards clients that request static HTML content as we
    normally deliver through the web UI
    """
    media_type = 'text/html'
    # 1. matched if no other renderer matches
    # 2. helps dispatch to the default engine renderer.
    format = ""
    template_name = "reports/report_display.html"

    def render(self, response_data, accepted_media_type=None, renderer_context=None):
        view = renderer_context['view']
        request = renderer_context["request"]
        response = renderer_context['response']

        ctx = {}
        # skip report gen if an exception occurred previously
        if response.exception:
            template = self.get_exception_template(response)
        else:
            # prepare engine
            ctx = response_data["ctx"]
            engine = response_data["engine"]
            if engine.provides_menus():  # if template provides menus, suppress the default ones.
                ctx['hidemenus'] = True
            print_target = request.GET.get('print', None)
            TemplateEngine.set_print_style(print_target)
            browser_type = request.GET.get('browser', None)
            TemplateEngine.set_browser_type(browser_type)
            TemplateEngine.set_global_context(
                {'page_number': 1, 'root_template': engine.template, 'hidemenus': ctx['hidemenus']})
            # prepare engine
            TemplateEngine.start_toc_session()
            target = request.GET.get('colorize', None)
            if target is not None:
                engine.calculate_random_colors(0., target)
            # core render
            try:
                ctx['HTML'] = super().render(response_data, accepted_media_type=accepted_media_type,
                                             renderer_context=renderer_context)
            except Exception as render_error:
                ctx['HTML'] = get_render_error_html(render_error, target='Report', guid=engine.template.guid)
            ctx['HTML'] += TemplateEngine.end_toc_session()
            # get the template
            template_names = self.get_template_names(response, view)
            template = self.resolve_template(template_names)

        # django's template render
        context = self.get_template_context(ctx, renderer_context)
        return template.render(context, request=request)


class PPTXReportRenderer(ReportRenderer):
    """
    Targeted toward PPTX export outputs requested by the client
    """
    media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    format = "pptx"
    charset = None  # Since we're sending binary content with the content-type set
    render_style = 'binary'

    def render(self, response_data, accepted_media_type=None, renderer_context=None):
        try:
            return super().render(response_data, accepted_media_type=accepted_media_type,
                                  renderer_context=renderer_context)
        except Exception as e:
            raise APIException(f"Unable to render report as PPTX: {e}")
