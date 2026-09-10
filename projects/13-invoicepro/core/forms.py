"""InvoicePro forms."""
from decimal import Decimal

from django import forms
from django.forms import inlineformset_factory

from .models import Client, Expense, Invoice, LineItem, Payment


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ["name", "company", "email", "address", "tax_id", "default_tax_rate", "default_terms_days"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "company": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "tax_id": forms.TextInput(attrs={"class": "form-control"}),
            "default_tax_rate": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "default_terms_days": forms.NumberInput(attrs={"class": "form-control", "min": "0", "max": "180"}),
        }


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ["client", "issue_date", "due_date", "tax_rate", "discount", "notes"]
        widgets = {
            "client": forms.Select(attrs={"class": "form-control"}),
            "issue_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
            "due_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
            "tax_rate": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0", "max": "99"}),
            "discount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3,
                                           "placeholder": "Payment details, bank account, thank-you note…"}),
        }

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["issue_date"].input_formats = ["%Y-%m-%d"]
        self.fields["due_date"].input_formats = ["%Y-%m-%d"]
        if owner is not None:
            self.fields["client"].queryset = Client.objects.filter(owner=owner)

    def clean(self):
        data = super().clean()
        issue, due = data.get("issue_date"), data.get("due_date")
        if issue and due and due < issue:
            self.add_error("due_date", "The due date cannot be before the issue date.")
        discount = data.get("discount")
        if discount and discount < 0:
            self.add_error("discount", "Discount cannot be negative.")
        return data


class LineItemForm(forms.ModelForm):
    class Meta:
        model = LineItem
        fields = ["description", "quantity", "unit_price", "order"]
        widgets = {
            "description": forms.TextInput(attrs={"class": "form-control", "placeholder": "Design work — March"}),
            "quantity": forms.NumberInput(attrs={"class": "form-control", "step": "0.25", "min": "0.01"}),
            "unit_price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "order": forms.HiddenInput(),
        }

    def clean_quantity(self):
        quantity = self.cleaned_data["quantity"]
        if quantity <= 0:
            raise forms.ValidationError("Quantity must be greater than zero.")
        return quantity


LineItemFormSet = inlineformset_factory(Invoice, LineItem, form=LineItemForm, extra=3, can_delete=True,
                                        min_num=1, validate_min=True)


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["amount", "method", "reference", "paid_on", "note"]
        widgets = {
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0.01"}),
            "method": forms.Select(attrs={"class": "form-control"}),
            "reference": forms.TextInput(attrs={"class": "form-control", "placeholder": "Txn / cheque number"}),
            "paid_on": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
            "note": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, invoice=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.invoice = invoice
        self.fields["paid_on"].input_formats = ["%Y-%m-%d"]
        if invoice is not None:
            self.fields["amount"].initial = invoice.balance
            self.fields["paid_on"].initial = invoice.due_date and __import__("django.utils.timezone",
                                                                             fromlist=["timezone"]).localdate()

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= 0:
            raise forms.ValidationError("Payments must be greater than zero.")
        if self.invoice is not None and amount > self.invoice.balance:
            raise forms.ValidationError(
                f"That is more than the outstanding balance of {self.invoice.balance}.")
        return amount


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ["description", "amount", "category", "incurred_on"]
        widgets = {
            "description": forms.TextInput(attrs={"class": "form-control"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "category": forms.TextInput(attrs={"class": "form-control", "placeholder": "Software / travel / hardware"}),
            "incurred_on": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["incurred_on"].input_formats = ["%Y-%m-%d"]
