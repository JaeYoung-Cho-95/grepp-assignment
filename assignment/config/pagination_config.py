from rest_framework.pagination import CursorPagination
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

class CustomCursorPagination(CursorPagination):
    page_size = 20
    page_size_query_param = 'limit'
    max_page_size = 100
    ordering = ('-created_at', '-id')  # 기본 정렬(고유 타이브레이커 -id 포함)

    def paginate_queryset(self, queryset, request, view=None):
        # 정렬 결정(커서/오프셋 공통)
        sort = request.query_params.get('sort', 'created')
        if sort == 'popular':
            self.ordering = ('-registrations_count', '-created_at', '-id')
        else:
            self.ordering = ('-created_at', '-id')

        # page가 있으면 오프셋 모드(임의 페이지 점프)
        page = request.query_params.get('page')
        if page is not None:
            try:
                page = int(page)
            except (TypeError, ValueError):
                raise ValidationError({'page': '정수여야 합니다.'})
            if page < 1:
                raise ValidationError({'page': '1 이상이어야 합니다.'})

            limit = self.get_page_size(request) or self.page_size
            if limit <= 0:
                raise ValidationError({'limit': '1 이상이어야 합니다.'})

            offset = (page - 1) * limit
            self._offset_mode = True
            self._page = page
            self._limit = limit

            qs = queryset.order_by(*self.ordering)
            self._results = list(qs[offset: offset + limit])
            self._returned = len(self._results)
            return self._results

        # 기본: 커서 모드
        self._offset_mode = False
        return super().paginate_queryset(queryset.order_by(*self.ordering), request, view)

    def get_paginated_response(self, data):
        if getattr(self, '_offset_mode', False):
            next_page = self._page + 1 if self._returned == self._limit else None
            prev_page = self._page - 1 if self._page > 1 else None
            return Response({
                'meta': {'page': self._page, 'limit': self._limit, 'next_page': next_page, 'prev_page': prev_page},
                'results': data,
            })
        return super().get_paginated_response(data)