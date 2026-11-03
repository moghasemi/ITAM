"""کلاس‌های پایه نماها: زمینه صفحه، لاگ ممیزی و پیام‌ها."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .utils import log_action, model_changes, snapshot_instance


class PageContextMixin:
    """اطلاعات مشترک سربرگ صفحه."""

    page_title = ""
    page_subtitle = ""
    active_menu = ""
    breadcrumbs: list = []
    back_url = ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("page_title", self.page_title)
        context.setdefault("page_subtitle", self.page_subtitle)
        context.setdefault("active_menu", self.active_menu)
        context.setdefault("breadcrumbs", self.breadcrumbs)
        context.setdefault("back_url", self.back_url)
        return context


class AuditMixin:
    """ثبت خودکار رخداد در لاگ ممیزی."""

    audit_note = ""
    success_message = ""

    def _audit(self, action: str, obj, changes: dict | None = None, note: str = ""):
        log_action(
            action,
            obj,
            changes=changes or {},
            note=note or self.audit_note,
            user=getattr(self.request, "user", None),
        )

    def _flash(self, message: str):
        if message:
            messages.success(self.request, message)


class BaseListView(LoginRequiredMixin, PageContextMixin, ListView):
    paginate_by = 20
    filter_form_class = None
    template_name = ""

    def get_filter_form(self):
        if not self.filter_form_class:
            return None
        return self.filter_form_class(self.request.GET or None)

    def apply_filters(self, queryset, cleaned):
        return queryset

    def get_queryset(self):
        queryset = super().get_queryset()
        form = self.get_filter_form()
        if form is not None and form.is_valid():
            queryset = self.apply_filters(queryset, form.cleaned_data)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = self.get_filter_form()
        context["filter_form"] = form
        context["total_count"] = self.get_queryset().count()
        params = self.request.GET.copy()
        params.pop("page", None)
        context["querystring"] = params.urlencode()
        return context


class BaseDetailView(LoginRequiredMixin, PageContextMixin, DetailView):
    pass


class BaseCreateView(LoginRequiredMixin, AuditMixin, PageContextMixin, CreateView):
    success_url_name = ""

    def get_success_url(self):
        if self.success_url_name:
            from django.urls import reverse

            return reverse(self.success_url_name, args=[self.object.pk])
        return super().get_success_url()

    def form_valid(self, form):
        response = super().form_valid(form)
        self._audit("create", self.object)
        self._flash(self.success_message or "با موفقیت ثبت شد.")
        return response


class BaseUpdateView(LoginRequiredMixin, AuditMixin, PageContextMixin, UpdateView):
    success_url_name = ""
    audit_fields: tuple = ()

    def get_success_url(self):
        if self.success_url_name:
            from django.urls import reverse

            return reverse(self.success_url_name, args=[self.object.pk])
        return super().get_success_url()

    def form_valid(self, form):
        before = snapshot_instance(self.object, self.audit_fields or None)
        response = super().form_valid(form)
        after = snapshot_instance(self.object, self.audit_fields or None)
        self._audit("update", self.object, changes=model_changes(before, after))
        self._flash(self.success_message or "تغییرات ذخیره شد.")
        return response


class BaseDeleteView(LoginRequiredMixin, AuditMixin, PageContextMixin, DeleteView):
    def form_valid(self, form):
        obj = self.get_object()
        label = str(obj)
        response = super().form_valid(form)
        log_action(
            "delete",
            None,
            model_name=obj.__class__.__name__,
            object_id=getattr(obj, "pk", ""),
            object_label=label,
            user=getattr(self.request, "user", None),
        )
        self._flash(self.success_message or "رکورد حذف شد.")
        return response


def apply_search(queryset, term: str, fields: list[str]):
    """اعمال جستجوی ساده روی چند فیلد."""
    term = (term or "").strip()
    if not term:
        return queryset
    condition = Q()
    for field in fields:
        condition |= Q(**{f"{field}__icontains": term})
    return queryset.filter(condition).distinct()
