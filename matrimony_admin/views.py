from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.views.generic import FormView
from django.urls import reverse_lazy
from .forms import AdminLoginForm,AdminProfileForm
from U_auth.permissions import *

from U_auth.models import costume_user
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncDay
from subscription.models import Payment
from django.utils import timezone
from datetime import timedelta

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
            labels_subscribers.append(day.strftime('%b %d'))
            subscribers_count = Payment.objects.filter(created_at__date=day).count()
            data_subscribers.append(subscribers_count)

        # todays subscribers
        total_subscribers = []
        subscribers_count = Payment.objects.filter(status='200').count()
        unsubscribers_count = Payment.objects.filter(status='unsub').count()
        total_subscribers = [subscribers_count, unsubscribers_count]

        # Get the current month and year
        now = timezone.now()
        first_day_of_month = now.replace(day=1)
        last_day_of_month = (first_day_of_month + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        # Fetch users who joined this month
        new_users = costume_user.objects.filter(date_joined__gte=first_day_of_month, date_joined__lte=last_day_of_month)

        # Initialize arrays for arrivals and active users
        arrivals = [0] * 31  # Array for the days of the month (1-31)
        active_users = [0] * 31  # Array for the active users each day

        # Count new users per day
        for user in new_users:
            arrivals[user.date_joined.day - 1] += 1

        for day in range(1, 31):
            # Fetch the count of active users for the given day
            active_users[day - 1] = costume_user.objects.filter(last_login__date=now.replace(day=day).date()).count()

        # Add data to context
        context['label'] = list(range(1, 32))  # Days of the month
        context['arrivals'] = arrivals
        context['active_users'] = active_users


        # Aggregate the total revenue for payments with status 200
        matrimony_revenue = Payment.objects.filter(status=200).aggregate(total_revenue=Sum('amount'))['total_revenue']
        context['matrimony_revenue'] = matrimony_revenue
        #Debugging
        # print(matrimony_revenue,'matrimony_revenue')


        context['labels_subscribers'] = labels_subscribers
        context['data_subscribers'] = data_subscribers
        context['total_subscribers'] = total_subscribers

        return context

def usr_mng(request):
    return render(request,"user_manage.html")

class AdminLoginView(CheckSuperUserAuthendicated ,FormView):
    template_name = 'admin_login.html'
    form_class = AdminLoginForm
    success_url = reverse_lazy('admin_home')

    def form_valid(self, form):
        email = form.cleaned_data.get('email')
        password = form.cleaned_data.get('password')

        user = authenticate(email=email, password=password)
        if user is not None:
            login(self.request, user)
            return super().form_valid(form)
        else:
            messages.error(self.request, 'Invalid credentials')
            return self.form_invalid(form)
    
class AdminLogoutView(CheckSuperUserNotAuthendicated ,TemplateView):
    def get(self, request, *args, **kwargs):
        logout(request)
        return redirect('admin_login')

class FinancialManagement(TemplateView):
    template_name = "financial_management.html"


class NotifcationManagement(TemplateView):
    template_name = "notification_management.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['select_options'] = ['User 1', 'User 2', 'User 3']
        # Add other context variables if needed
        return context
    

# def admin_profile(request):
#     return render(request,"admin_profile.html")


class admin_profile(CheckSuperUserNotAuthendicated,FormView):
    template_name = "admin_profile.html"
    form_class = AdminProfileForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['admin_details'] = self.request.user
        return context
    