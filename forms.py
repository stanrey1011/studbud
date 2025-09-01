from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import StringField, PasswordField, TextAreaField, SelectField, SubmitField, IntegerField, SelectMultipleField, BooleanField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError
import json

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class UserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=80)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    role = SelectField('Role', choices=[('user', 'User'), ('admin', 'Admin')])
    submit = SubmitField('Create User')

class PasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired(), Length(min=6)])
    submit = SubmitField('Update Password')

class TestForm(FlaskForm):
    name = StringField('Test Name', validators=[DataRequired()])
    description = TextAreaField('Description')
    time_limit = IntegerField('Time Limit (minutes)', default=0, validators=[NumberRange(min=0)])
    num_questions = IntegerField('Number of Questions', validators=[DataRequired(), NumberRange(min=1)], default=1)
    submit = SubmitField('Save Test')

class QuestionForm(FlaskForm):
    type = SelectField('Type', choices=[
        ('mcq', 'Multiple Choice'),
        ('mrq', 'Multiple Response'),
        ('tf', 'True/False'),
        ('flashcard', 'Flashcard'),
        ('match', 'Match')
    ], validators=[DataRequired()])
    text = TextAreaField('Question Text', validators=[DataRequired()])
    options = TextAreaField('Options (JSON array for mcq/mrq/tf, e.g., ["A. Option", "B. Option"], or JSON object for match, e.g., {"terms": [{"id": 1, "text": "KEK"}], "definitions": [{"id": 1, "text": "Key Encryption Key"}]})', validators=[DataRequired()])
    correct = TextAreaField('Correct Answer(s) (for mcq/tf: single value, e.g., "A" or "true"; for mrq: comma-separated, e.g., "A, B"; for match: JSON object, e.g., {"1": "1", "2": "2"})', validators=[DataRequired()])
    explanation = TextAreaField('Explanation', validators=[Optional()])
    image = FileField('Upload Topology/Image')
    delete_image = BooleanField('Delete current image')
    submit = SubmitField('Save Question')

    def validate_options(self, field):
        if self.type.data in ['mcq', 'mrq', 'tf']:
            try:
                json.loads(field.data)
            except json.JSONDecodeError:
                raise ValidationError('Options must be a valid JSON array for mcq, mrq, or tf.')
        elif self.type.data == 'match':
            try:
                data = json.loads(field.data)
                if not isinstance(data, dict) or 'terms' not in data or 'definitions' not in data:
                    raise ValidationError('Options for match must be a JSON object with "terms" and "definitions" arrays.')
                term_ids = set()
                for term in data['terms']:
                    if not isinstance(term, dict) or 'id' not in term or 'text' not in term:
                        raise ValidationError('Each term must have "id" and "text".')
                    if str(term['id']) in term_ids:
                        raise ValidationError(f'Duplicate term ID: {term["id"]}.')
                    term_ids.add(str(term['id']))
                definition_ids = set()
                for definition in data['definitions']:
                    if not isinstance(definition, dict) or 'id' not in definition or 'text' not in definition:
                        raise ValidationError('Each definition must have "id" and "text".')
                    if str(definition['id']) in definition_ids:
                        raise ValidationError(f'Duplicate definition ID: {definition["id"]}.')
                    definition_ids.add(str(definition['id']))
            except json.JSONDecodeError:
                raise ValidationError('Options for match must be valid JSON.')

    def validate_correct(self, field):
        if self.type.data in ['mcq', 'tf']:
            try:
                json.loads(field.data)
                raise ValidationError('Correct answer for mcq or tf must be a single value, not JSON.')
            except json.JSONDecodeError:
                pass
        elif self.type.data == 'mrq':
            try:
                json.loads(field.data)
                raise ValidationError('Correct answer for mrq must be comma-separated values, not JSON.')
            except json.JSONDecodeError:
                pass
        elif self.type.data == 'match':
            try:
                data = json.loads(field.data)
                if not isinstance(data, dict):
                    raise ValidationError('Correct answer for match must be a JSON object mapping term IDs to definition IDs.')
                options = json.loads(self.options.data)
                term_ids = {str(term['id']) for term in options.get('terms', [])}
                definition_ids = {str(definition['id']) for definition in options.get('definitions', [])}
                for term_id, def_id in data.items():
                    if term_id not in term_ids:
                        raise ValidationError(f'Term ID {term_id} not found in options.terms.')
                    if def_id not in definition_ids:
                        raise ValidationError(f'Definition ID {def_id} not found in options.definitions.')
            except json.JSONDecodeError:
                raise ValidationError('Correct answer for match must be valid JSON.')

class ImportForm(FlaskForm):
    json_file = FileField('Upload JSON File')
    overwrite = BooleanField('Overwrite Existing Tests')
    submit = SubmitField('Import')

class SimStartForm(FlaskForm):
    custom_time = IntegerField('Timer (minutes, 0 for unlimited)', default=0, validators=[NumberRange(min=0)])
    submit = SubmitField('Start Sim')