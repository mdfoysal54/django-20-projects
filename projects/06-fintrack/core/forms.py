"""FinTrack forms — accounts, categories, transactions, transfers, budgets, CSV import."""
from decimal import Decimal, InvalidOperation

from django import forms
from django.utils import timezone

from .models import Account, Budget, Category, Transaction


class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ["name", "kind", "opening_balance", "currency", "icon"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Salary account"}),
            "kind": forms.Select(attrs={"class": "form-control"}),
            "opening_balance": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "currency": forms.TextInput(attrs={"class": "form-control", "maxlength": 8}),
            "icon": forms.TextInput(attrs={"class": "form-control", "maxlength": 8}),
        }


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "kind", "icon", "color"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Groceries"}),
            "kind": forms.Select(attrs={"class": "form-control"}),
            "icon": forms.TextInput(attrs={"class": "form-control", "maxlength": 8}),
            "color": forms.TextInput(attrs={"class": "form-control", "type": "color", "style": "height:44px"}),
        }


class TransactionForm(forms.ModelForm):
    """Amount is entered as a positive number; the sign is derived from kind."""

    class Meta:
        model = Transaction
        fields = ["account", "kind", "category", "amount", "note", "date"]
        widgets = {
            "account": forms.Select(attrs={"class": "form-control"}),
            "kind": forms.Select(attrs={"class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-control"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0.01",
                                               "placeholder": "0.00"}),
            "note": forms.TextInput(attrs={"class": "form-control", "placeholder": "What was it for?"}),
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        }

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = user.accounts.filter(archived=False)
        self.fields["category"].queryset = user.categories.all()
        self.fields["category"].required = False
        self.fields["kind"].choices = [
            (Transaction.Kind.EXPENSE, "Expense"), (Transaction.Kind.INCOME, "Income"),
        ]
        self.fields["date"].initial = timezone.localdate()

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= 0:
            raise forms.ValidationError("Enter the amount as a positive number.")
        if amount > Decimal("10000000"):
            raise forms.ValidationError("That amount looks too large — double-check it.")
        return amount

    def clean(self):
        cleaned = super().clean()
        category, kind = cleaned.get("category"), cleaned.get("kind")
        if category and kind:
            wanted = Category.Kind.EXPENSE if kind == Transaction.Kind.EXPENSE else Category.Kind.INCOME
            if category.kind != wanted:
                self.add_error("category", f"That category is for {wanted} transactions.")
        # The user types a positive number; apply the model's sign convention
        # here so the instance passes model validation during _post_clean().
        amount = cleaned.get("amount")
        if amount is not None and kind:
            cleaned["amount"] = -amount if kind == Transaction.Kind.EXPENSE else amount
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.user = self.user
        if commit:
            instance.save()
        return instance


class TransferForm(forms.Form):
    from_account = forms.ModelChoiceField(queryset=Account.objects.none(),
                                          widget=forms.Select(attrs={"class": "form-control"}))
    to_account = forms.ModelChoiceField(queryset=Account.objects.none(),
                                        widget=forms.Select(attrs={"class": "form-control"}))
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"),
                                widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}))
    note = forms.CharField(required=False, max_length=200,
                           widget=forms.TextInput(attrs={"class": "form-control"}))
    date = forms.DateField(widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}))

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        accounts = user.accounts.filter(archived=False)
        self.fields["from_account"].queryset = accounts
        self.fields["to_account"].queryset = accounts
        self.fields["date"].initial = timezone.localdate()

    def clean(self):
        cleaned = super().clean()
        source, target = cleaned.get("from_account"), cleaned.get("to_account")
        if source and target and source.pk == target.pk:
            self.add_error("to_account", "Pick two different accounts.")
        return cleaned


class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ["category", "amount", "year", "month"]
        widgets = {
            "category": forms.Select(attrs={"class": "form-control"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0.01"}),
            "year": forms.NumberInput(attrs={"class": "form-control", "min": 2000, "max": 2100}),
            "month": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = user.categories.filter(kind=Category.Kind.EXPENSE)
        today = timezone.localdate()
        self.fields["year"].initial = today.year
        self.fields["month"].initial = today.month

    def clean(self):
        cleaned = super().clean()
        category, year, month = cleaned.get("category"), cleaned.get("year"), cleaned.get("month")
        if category and year and month:
            existing = Budget.objects.filter(user=self.user, category=category, year=year, month=month)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                self.add_error(None, "You already have a budget for that category this month — edit it instead.")
        return cleaned


class CSVImportForm(forms.Form):
    """Upload a CSV of transactions: date,amount,note[,category]

    * amount is signed (negative = expense) or may carry an explicit 4th column;
    * rows are validated per line and reported back (added / skipped + reasons);
    * the file is size-capped here and extension-checked in the view.
    """

    file = forms.FileField(
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".csv,text/csv"}),
        help_text="CSV with columns: date (YYYY-MM-DD), amount (signed), note, category (optional).",
    )
    account = forms.ModelChoiceField(queryset=Account.objects.none(),
                                     widget=forms.Select(attrs={"class": "form-control"}))
    max_rows = forms.IntegerField(initial=500, min_value=1, max_value=2000,
                                  widget=forms.NumberInput(attrs={"class": "form-control"}))

    MAX_BYTES = 1 * 1024 * 1024  # 1 MB

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = user.accounts.filter(archived=False)

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if not upload.name.lower().endswith(".csv"):
            raise forms.ValidationError("Please upload a .csv file.")
        if upload.size > self.MAX_BYTES:
            raise forms.ValidationError("CSV must be 1 MB or smaller.")
        return upload
