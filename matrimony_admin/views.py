import json
import os
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect
from django.views.generic import TemplateView, DetailView, ListView
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.views.generic import FormView
from django.urls import reverse_lazy
from .forms import AdminLoginForm, AdminProfileForm, NotificationDetailsForm
from .models import BlockedUserInfo
from U_auth.permissions import *

from U_auth.models import costume_user
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncDay
from subscription.models import Payment
from django.utils import timezone
from datetime import timedelta

from U_auth.models import *
from matrimony_admin.models import Subscription
from U_auth.permissions import *
from django.db.models import Count, Sum, F, Case, When, DecimalField
from django.db.models.functions import TruncMonth, TruncDay
from datetime import datetime
from U_messages.models import NotificationDetails, AmidUsers


class AdminHomeView(CheckSuperUserNotAuthendicated, TemplateView):
    template_name = "admin_home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get today's date
        today = timezone.now().date()

        # 1. Data for the subscribers chart
        labels_subscribers = []
        data_subscribers = []
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            labels_subscribers.append(day.strftime("%b %d"))
            subscribers_count = Payment.objects.filter(created_at__date=day).count()
            data_subscribers.append(subscribers_count)

        # total subscribers
        total_subscribers = []
        subscribers_count = Payment.objects.filter(status="200").count()
        unsubscribers_count = Payment.objects.filter(status="unsub").count()
        total_subscribers = [subscribers_count, unsubscribers_count]

        # 3. Data for the income chart (Revenue per day for the current month)
        daily_financial_data = (
            Add_expense.objects.filter(date__month=today.month, date__lte=today)
            .annotate(day=TruncDay("date"))
            .values("day")
            .annotate(
                daily_income=Sum(
                    Case(
                        When(cr__gt=F("dr"), then=F("cr") - F("dr")),
                        default=0,
                        output_field=DecimalField(),
                    )
                ),
                daily_expense=Sum(
                    Case(
                        When(dr__gt=F("cr"), then=F("dr") - F("cr")),
                        default=0,
                        output_field=DecimalField(),
                    )
                ),
            )
            .order_by("day")
        )

        # Prepare daily income and expense data for the chart
        days = [
            day for day in range(1, today.day + 1)
        ]  # Days 1 to current day of the month
        daily_income = {
            entry["day"].day: float(entry["daily_income"] or 0)
            for entry in daily_financial_data
        }
        daily_expense = {
            entry["day"].day: float(entry["daily_expense"] or 0)
            for entry in daily_financial_data
        }

        income_data = [daily_income.get(day, 0) for day in days]
        expense_data = [daily_expense.get(day, 0) for day in days]

        total_income = sum(income_data)
        total_expense = sum(expense_data)
        profit = total_income - total_expense

        # Add financial data to context
        context["labels"] = days
        context["income_data"] = income_data
        context["expense_data"] = expense_data
        context["total_income"] = total_income
        context["total_expense"] = total_expense
        context["profit"] = profit

        # customer arrivals
        # Get the current month and year
        now = timezone.now()
        first_day_of_month = now.replace(day=1)
        last_day_of_month = (first_day_of_month + timedelta(days=32)).replace(
            day=1
        ) - timedelta(days=1)
        # Fetch users who joined this month
        new_users = costume_user.objects.filter(
            date_joined__gte=first_day_of_month, date_joined__lte=last_day_of_month
        )

        # Initialize arrays for arrivals and active users
        arrivals = [0] * 31  # Array for the days of the month (1-31)
        active_users = [0] * 31  # Array for the active users each day

        # Count new users per day
        for user in new_users:
            arrivals[user.date_joined.day - 1] += 1

        for day in range(1, 31):
            # Fetch the count of active users for the given day
            active_users[day - 1] = costume_user.objects.filter(
                last_login__date=now.replace(day=day).date()
            ).count()

        # Add data to context
        context["label"] = list(range(1, 32))  # Days of the month
        context["arrivals"] = arrivals
        context["active_users"] = active_users

        current_active = costume_user.objects.filter(
            last_login__date=now.date()
        ).count()
        total_users = costume_user.objects.count()
        blocked_users = BlockedUserInfo.objects.select_related(
            "user", "user__user_details"
        ).all()

        # Aggregate the total revenue for payments with status 200
        matrimony_revenue = Payment.objects.filter(status=200).aggregate(
            total_revenue=Sum("amount")
        )["total_revenue"]

        context["matrimony_revenue"] = matrimony_revenue
        context["current_active"] = current_active
        context["total_users"] = total_users
        context["subscribers_count"] = subscribers_count
        context["total_income"] = total_income
        context["income_data"] = income_data
        context["labels_subscribers"] = labels_subscribers
        context["data_subscribers"] = data_subscribers
        context["total_subscribers"] = total_subscribers
        context["blocked_users"] = blocked_users

        return context


def usr_mng(request):
    return render(request, "user_manage.html")


class AdminLoginView(CheckSuperUserAuthendicated, FormView):
    template_name = "admin_login.html"
    form_class = AdminLoginForm
    success_url = reverse_lazy("admin_home")

    def form_valid(self, form):
        email = form.cleaned_data.get("email")
        password = form.cleaned_data.get("password")

        user = authenticate(email=email, password=password)
        if user is not None:
            login(self.request, user)
            return super().form_valid(form)
        else:
            messages.error(self.request, "Invalid credentials")
            return self.form_invalid(form)


class AdminLogoutView(CheckSuperUserNotAuthendicated, TemplateView):
    def get(self, request, *args, **kwargs):
        logout(request)
        return redirect("admin_login")


class FinancialManagement(TemplateView):
    template_name = "financial_management.html"


class NotifcationManagement(FormView):
    template_name = "notification_management.html"
    form_class = NotificationDetailsForm
    success_url = "notification_management"

    def post(self, request: HttpRequest, *args: str, **kwargs: dict) -> HttpResponse:
        form = self.form_class(request.POST)
        if form.is_valid():
            notification = form.save(commit=True)
        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # context = ['users'] = costume_user.objects.all()
        context["select_options"] = ["User 1", "User 2", "User 3"]
        # Add other context variables if needed
        return context

    # def get_success_url(self) -> str:
    #     return reverse_lazy('notification_management')


# def admin_profile(request):
#     return render(request,"admin_profile.html")


class admin_profile(CheckSuperUserNotAuthendicated, FormView):
    template_name = "admin_profile.html"
    form_class = AdminProfileForm


class SubscriptionManagementView(ListView):
    model = Subscription
    template_name = "admin_subscription.html"
    context_object_name = "subscriptions"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


# arjun

from django.views.generic import CreateView, ListView
from django.urls import reverse_lazy
from .models import Add_expense
from .forms import AddExpenseForm  # Assuming you have a form for your model


class AddExpenseView(CreateView):
    model = Add_expense
    form_class = AddExpenseForm  # Use the form you created for AddExpense
    template_name = "add_expense.html"  # Your template for adding expenses
    success_url = reverse_lazy("add_expense")  # Redirect after successful submission

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["expenses"] = (
            Add_expense.objects.all()
        )  # Fetch all expenses for display
        return context
