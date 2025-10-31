from django.urls import path
from . import views

urlpatterns = [
    path('transactions/', views.WalletTransactionListView.as_view(), name='wallet-transactions'),
    path('bank-accounts/', views.BankAccountListView.as_view(), name='bank-accounts'),
    path('bank-accounts/<int:pk>/', views.BankAccountDetailView.as_view(), name='bank-account-detail'),
    path('withdraw/', views.request_withdrawal, name='request-withdrawal'),
    path('fund-escrow/', views.fund_escrow, name='fund-escrow'),
    path('verify-bank-account/', views.verify_bank_account_view, name='verify-bank-account'),
    path('summary/', views.wallet_summary, name='wallet-summary'),
    path('supported-banks/', views.get_supported_banks, name='supported-banks'),
]