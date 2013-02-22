# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import copy

from django import forms
from django.utils.translation import ugettext
from django.utils.encoding import smart_unicode
from django.db.models import Model
from django.utils.datastructures import SortedDict
from django.utils.translation import ugettext_lazy as _

from django_intranet_stuff.utils.choices import Choices

__all__ = (
    'FIELD_STATE',
    'TreeForm', 'TreeFormField', 'ModelChoiceField', 'MulticModelChoiceField',
    'CharField', 'DateField', 'EmailField', 'BooleanField', 'ChoiceField',
)

# 'IntegerField','TimeField','DateTimeField', 'TimeField','RegexField',
# 'FileField', 'ImageField', 'URLField','NullBooleanField',
# 'MultipleChoiceField',
# 'ComboField', 'MultiValueField', 'FloatField', 'DecimalField',
    # 'SplitDateTimeField', 'IPAddressField', 'GenericIPAddressField', 'FilePathField',
# 'SlugField', 'TypedChoiceField', 'TypedMultipleChoiceField'

FIELD_STATE = Choices(
    REQUIRED = ('required', 'required'),
    NORMAL = ('normal', 'normal'),
    READONLY = ('readonly', 'readonly'),
)


class Field(object):

    creation_counter = 0

    def __init__(self, label='', state=FIELD_STATE.NORMAL, default='',
                empty_label=u"---------", help_text='', *args, **kwargs):

        super(Field, self).__init__()

        self.creation_counter = Field.creation_counter
        Field.creation_counter += 1

        self.label = label
        self.state = state
        self.empty_label = empty_label
        self.help_text = help_text
        self.args = args
        self.kwargs = kwargs
        self.default = default

    def set_form_and_name(self, form, name):
        self.form = form
        self.name = name

    def clean(self, new_value, old_value, required):
        result, has_error, changed = None, False, False
        try:
            dj_field = self.get_dj_field(required)
            result = dj_field.clean(new_value)
            if self.value_is_changed(result, old_value):
                changed = (old_value, result)
        except forms.ValidationError, e:
            errors = e.messages
            for error_msg in errors:
                self.set_error(error_msg)
            has_error = True

        return result, has_error, changed

    def value_is_changed(self, new_value, old_value):
        return new_value == old_value

    def value_from_datadict(self, name, data):
        return data.get(name, self.default)

    def get_dj_field(self, required=False):
        raise NotImplemented()


    def as_dict(self, name, value, state):
        field_dict = {
            'label': ugettext(self.label) if self.label else self.label,
            'name': name,
            'value': value,
            'help_text': ugettext(self.help_text) if self.help_text else self.help_text,
            'required': state==FIELD_STATE.REQUIRED,
            'readonly': state==FIELD_STATE.READONLY,
            'type': self.__class__.__name__,
        }

        return field_dict

    def set_error(self, error_msg):
        error_list = self.form._errors.setdefault(self.name, [])
        error_list.append(error_msg)


class BooleanField(Field):
    def __init__(self, default=False, *args, **kwargs):
        kwargs['default'] = default
        super(BooleanField, self).__init__(*args, **kwargs)

    def get_dj_field(self, required=False):
        return forms.BooleanField(required=required,
            *self.args, **self.kwargs)


class DateField(Field):
    def get_dj_field(self, required=False):
        return forms.DateField(required=required,
            *self.args, **self.kwargs)


class CharField(Field):
    def get_dj_field(self, required=False):
        return forms.CharField(required=required,
            *self.args, **self.kwargs)


class EmailField(Field):
    def get_dj_field(self, required=False):
        return forms.EmailField(required=required,
            *self.args, **self.kwargs)


class ChoiceField(Field):
    def __init__(self, choices=(), *args, **kwargs):
        super(ChoiceField, self).__init__(*args, **kwargs)
        self.choices = choices

    def get_dj_field(self, required=False):
        return forms.ChoiceField(required=required, choices=self.choices,
            *self.args, **self.kwargs)

    def as_dict(self, *args, **kwargs):
        field_dict = super(ChoiceField, self).as_dict(*args, **kwargs)
        choices = []
        if self.empty_label is not None:
            choices.append({'value': '', 'name': self.empty_label})
        choices += [{
            'value': v,
            'name': ugettext(n)
            } for v,n in self.choices]
        field_dict['choices'] = choices
        return field_dict


class ModelChoiceField(Field):
    def __init__(self, queryset, *args, **kwargs):
        super(ModelChoiceField, self).__init__(*args, **kwargs)
        self.queryset = queryset

    def get_dj_field(self, required=False):
        return forms.ModelChoiceField(
            queryset=self.queryset,
            required=required,
            *self.args, **self.kwargs)

    def as_dict(self, *args, **kwargs):
        field_dict = super(ModelChoiceField, self).as_dict(*args, **kwargs)

        def choice_gen():
            if self.empty_label is not None:
                yield ('', self.field.empty_label)
            for obj in self.queryset.all():
                yield (obj.pk, smart_unicode(obj))


        choices = [{'value':v,'name':n} for v,n in choice_gen()]
        field_dict['choices'] = choices

        if isinstance(field_dict['value'], Model):
            field_dict['value'] = field_dict['value'].pk
        return field_dict


class TreeFormField(Field):
    def __init__(self, tree_form_cls, *args, **kwargs):
        self.tree_form_cls = tree_form_cls
        super(TreeFormField, self).__init__(*args, **kwargs)

    def clean(self, new_value, old_value, required):

        if not isinstance(new_value, list):
            self.set_error(_('Enter a valid value.'))
            self.set_error(_('Should be a list.'))
            return [], True, []

        def value_gen():
            for num, new_value_item in enumerate(new_value):
                try:
                    old_value_item = old_value[num]
                except IndexError:
                    old_value_item = {}
                yield new_value_item, old_value_item

        tree_forms = [self.tree_form_cls(data=nv, initial=ov,
                    parent_form=self.form) for nv, ov in value_gen()]

        has_error = False

        errors = [b.errors for b in tree_forms]
        has_error = any(errors)
        if has_error:
            self._set_error_list(errors)

        cleaned_data = [b.cleaned_data for b in tree_forms]
        changed = [b.changed for b in tree_forms]

        return cleaned_data, has_error, changed

    def as_dict(self, name, value, state):
        field_dict = super(TreeFormField, self).as_dict(name, value, state)
        tree_forms = (self.tree_form_cls(parent_form=self.form,
                                            initial=v) for v in value)
        field_dict['value'] = [b.as_dict() for b in tree_forms]
        return field_dict

    def _set_error_list(self, error_list):
        error_place = self.form._errors.setdefault(self.name, {})
        error_place['errors'] = error_list

    def set_error(self, error_msg):
        error_place = self.form._errors.setdefault(self.name, {})
        error_place = error_place.setdefault('all', [])
        error_place.append(error_msg)



class TreeFormMetaclass(type):
    def __new__(cls, name, bases, attrs):
        fields = []
        for field_name, obj in attrs.items():
            if isinstance(obj, Field):
                fields.append((field_name, attrs.pop(field_name)))
        fields.sort(key=lambda x: x[1].creation_counter)

        for base in bases[::-1]:
            if hasattr(base, 'base_fields'):
                fields = base.base_fields.items() + fields

        attrs['base_fields'] = SortedDict(fields)

        new_class = super(TreeFormMetaclass,
                                cls).__new__(cls, name, bases, attrs)

        return new_class


class BaseTreeForm(object):

    def __init__(self, data=None, initial=None, parent_form=None):
        # print self.__class__.__name__, parent_form
        self.data = data or {}
        self.initial = initial or {}
        self.parent_form = parent_form

        self._errors = None
        self.cleaned_data = {}
        self.changed = {}

        self.fields = copy.deepcopy(self.base_fields)

        for name, field in self.fields.iteritems():
            field.set_form_and_name(self, name)

        self.fields_state = self.prepare_fields_state()

    def prepare_fields_state(self):
        _fields = self.fields.iteritems()
        return dict((name, f.state) for name, f in _fields)

    def _clean_fields(self):
        self._errors = {}

        for name, field in self.fields.iteritems():
            old_value = field.value_from_datadict(name, self.initial)
            field_state = self.get_field_state(name)
            if field_state == FIELD_STATE.READONLY:
                self.cleaned_data[name] = old_value
                continue
            new_value = field.value_from_datadict(name, self.data)

            value, has_error, changed = field.clean(
                new_value=new_value,
                old_value=old_value,
                required=field_state==FIELD_STATE.REQUIRED
                )

            self.cleaned_data[name] = value

            if not has_error:
                if changed:
                    self.changed[name] = changed
                if hasattr(self, 'clean_%s' % name):
                    value = getattr(self, 'clean_%s' % name)()
                    self.cleaned_data[name] = value

    def set_error(self, field_name, error_msg):
        field = self.fields[field_name]
        field.set_error(error_msg)

    def _get_errors(self):
        if self._errors is None:
            self._clean_fields()
            self.cleaned_data = self.clean()
        return self._errors

    errors = property(_get_errors)

    def is_valid(self):
        return not bool(self.errors)

    def clean(self):
        return self.cleaned_data

    def get_field_state(self, name):
        return self.fields_state[name]

    def as_dict(self):
        result = {}
        for name, field in self.fields.iteritems():
            value = field.value_from_datadict(name, self.initial)
            state = self.get_field_state(name)
            result[name] = field.as_dict(name, value, state)
        return result

class TreeForm(BaseTreeForm):
    __metaclass__ = TreeFormMetaclass

