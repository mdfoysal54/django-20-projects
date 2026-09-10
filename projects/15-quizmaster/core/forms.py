"""QuizMaster forms."""
from django import forms

from .models import Category, Option, Question, Quiz


class QuizForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = ["title", "category", "description", "emoji", "visibility",
                  "pass_mark", "time_limit_minutes", "one_attempt_only", "shuffle_questions"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "Django fundamentals"}),
            "category": forms.Select(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "emoji": forms.TextInput(attrs={"class": "form-control", "maxlength": 8}),
            "visibility": forms.Select(attrs={"class": "form-control"}),
            "pass_mark": forms.NumberInput(attrs={"class": "form-control", "min": "1", "max": "100"}),
            "time_limit_minutes": forms.NumberInput(attrs={"class": "form-control", "min": "0", "max": "240"}),
        }

    def clean_pass_mark(self):
        value = self.cleaned_data["pass_mark"]
        if value < 1 or value > 100:
            raise forms.ValidationError("The pass mark is a percentage between 1 and 100.")
        return value

    def clean(self):
        data = super().clean()
        if data.get("visibility") != Quiz.Visibility.DRAFT and self.instance.pk:
            if not self.instance.questions.filter(active=True).exists():
                raise forms.ValidationError("Add at least one question before publishing.")
        return data


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ["kind", "text", "points", "explanation", "order", "active"]
        widgets = {
            "kind": forms.Select(attrs={"class": "form-control"}),
            "text": forms.TextInput(attrs={"class": "form-control", "placeholder": "Which HTTP method is idempotent?"}),
            "points": forms.NumberInput(attrs={"class": "form-control", "min": "1", "max": "20"}),
            "explanation": forms.TextInput(attrs={"class": "form-control",
                                                  "placeholder": "Shown to players after they submit."}),
            "order": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
        }

    def clean_text(self):
        text = self.cleaned_data["text"].strip()
        if len(text) < 8:
            raise forms.ValidationError("Write the full question (8+ characters).")
        return text


class OptionForm(forms.ModelForm):
    class Meta:
        model = Option
        fields = ["text", "is_correct", "order"]
        widgets = {
            "text": forms.TextInput(attrs={"class": "form-control", "placeholder": "Answer option"}),
            "order": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
        }


OptionFormSetFactory = forms.inlineformset_factory(Question, Option, form=OptionForm, extra=4,
                                                   can_delete=True, min_num=2, validate_min=True)


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "emoji"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "emoji": forms.TextInput(attrs={"class": "form-control", "maxlength": 8}),
        }


class TakeQuizForm(forms.Form):
    """One field per question; graded server-side on submit."""

    def __init__(self, *args, quiz=None, attempt=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.questions = []
        if quiz is None:
            return
        existing = {}
        if attempt is not None:
            existing = {a.question_id: a for a in attempt.answers.prefetch_related("selected_options")}
        questions = quiz.questions.filter(active=True).prefetch_related("options")
        if quiz.shuffle_questions:
            import random
            questions = list(questions)
            random.shuffle(questions)
        for question in questions:
            self.questions.append(question)
            name = f"q_{question.pk}"
            current = existing.get(question.pk)
            if question.kind in (Question.Kind.SINGLE, Question.Kind.TRUE_FALSE):
                self.fields[name] = forms.ModelChoiceField(
                    queryset=question.options.all(), required=False,
                    initial=current.selected_options.first() if current else None,
                    widget=forms.RadioSelect(attrs={"class": "answer-radio"}),
                    label=question.text)
            elif question.kind == Question.Kind.MULTI:
                self.fields[name] = forms.ModelMultipleChoiceField(
                    queryset=question.options.all(), required=False,
                    initial=current.selected_options.all() if current else None,
                    widget=forms.CheckboxSelectMultiple(attrs={"class": "answer-check"}),
                    label=question.text)
            else:
                self.fields[name] = forms.CharField(
                    required=False, max_length=240,
                    initial=current.text_answer if current else "",
                    widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Type your answer"}),
                    label=question.text)

    def save_answers(self, attempt):
        """Store the submitted answers (not yet graded)."""
        saved = 0
        for question in self.questions:
            value = self.cleaned_data.get(f"q_{question.pk}")
            answer = attempt.answer_for(question)
            if question.kind == Question.Kind.MULTI:
                answer.selected_options.set(value or [])
                answer.text_answer = ""
            elif question.kind == Question.Kind.SHORT:
                answer.selected_options.clear()
                answer.text_answer = (value or "").strip()
            else:
                answer.selected_options.set([value] if value else [])
                answer.text_answer = ""
            answer.save()
            saved += 1
        return saved
