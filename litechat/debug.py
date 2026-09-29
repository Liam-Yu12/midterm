from django.views.debug import SafeExceptionReporterFilter


class AlwaysSafeExceptionReporterFilter(SafeExceptionReporterFilter):
    """Mask `sensitive_variables` / `sensitive_post_parameters` even when DEBUG is on.

    Django's default filter only masks them when DEBUG is off, so the local debug
    page would otherwise show proxy keys held in llm.providers locals.
    """

    def is_active(self, request):
        return True
