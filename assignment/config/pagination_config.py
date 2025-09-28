from rest_framework.pagination import LimitOffsetPagination


class CustomPagination(LimitOffsetPagination):
    default_limit = 20
    max_limit = 100

    def get_limit(self, request):
        all_param = request.query_params.get('all')
        if isinstance(all_param, str) and all_param.lower() in ('1', 'true', 'yes'):
            return None
        return super().get_limit(request)