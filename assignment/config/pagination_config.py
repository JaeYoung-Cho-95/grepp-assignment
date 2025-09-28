from rest_framework.pagination import LimitOffsetPagination
from rest_framework.exceptions import ValidationError


class CustomPagination(LimitOffsetPagination):
    default_limit = 20
    max_limit = 100

    def get_limit(self, request):
        raw = request.query_params.get(self.limit_query_param)
        if raw is None:
            return super().get_limit(request)
        try:
            value = int(raw)
        except (TypeError, ValueError):
            raise ValidationError({self.limit_query_param: '정수여야 합니다.'})
        if value <= 0:
            raise ValidationError({self.limit_query_param: '1 이상이어야 합니다.'})
        if self.max_limit is not None and value > self.max_limit:
            raise ValidationError({self.limit_query_param: f'max_limit({self.max_limit}) 이하만 허용됩니다.'})
        return value
