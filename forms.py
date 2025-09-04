from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import StringField, PasswordField, TextAreaField, SelectField, SubmitField, IntegerField, SelectMultipleField, BooleanField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError
import json
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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
        ('match', 'Match')
    ], validators=[DataRequired()])
    text = TextAreaField('Question Text', validators=[DataRequired()])
    options = TextAreaField('Options (JSON array for mcq/mrq/tf, e.g., ["A. Option", "B. Option"], or JSON object for match, e.g., {"terms": [{"id": 1, "text": "KEK"}], "definitions": [{"id": 1, "text": "Key Encryption Key"}]})', validators=[DataRequired()])
    correct = SelectMultipleField('Correct Answer(s)', validators=[Optional()], coerce=str)
    match_mappings = StringField('Match Mappings (JSON)', validators=[Optional()])
    explanation = TextAreaField('Explanation', validators=[Optional()])
    image = FileField('Upload Topology/Image')
    delete_image = BooleanField('Delete current image')
    submit = SubmitField('Save Question')

    def validate_options(self, field):
        if self.type.data in ['mcq', 'mrq', 'tf']:
            try:
                options = json.loads(field.data)
                if not isinstance(options, list):
                    logger.error(f"Options is not a JSON array: {field.data}")
                    raise ValidationError('Options must be a valid JSON array for mcq, mrq, or tf.')
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in options: {field.data}, error: {str(e)}")
                raise ValidationError('Options must be a valid JSON array for mcq, mrq, or tf.')
        elif self.type.data == 'match':
            try:
                data = json.loads(field.data)
                if not isinstance(data, dict) or 'terms' not in data or 'definitions' not in data:
                    logger.error(f"Invalid match options format: {field.data}")
                    raise ValidationError('Options for match must be a JSON object with "terms" and "definitions" arrays.')
                term_ids = set()
                for term in data['terms']:
                    if not isinstance(term, dict) or 'id' not in term or 'text' not in term:
                        logger.error(f"Invalid term format: {term}")
                        raise ValidationError('Each term must have "id" and "text".')
                    if str(term['id']) in term_ids:
                        logger.error(f"Duplicate term ID: {term['id']}")
                        raise ValidationError(f'Duplicate term ID: {term["id"]}.')
                    term_ids.add(str(term['id']))
                definition_ids = set()
                for definition in data['definitions']:
                    if not isinstance(definition, dict) or 'id' not in definition or 'text' not in definition:
                        logger.error(f"Invalid definition format: {definition}")
                        raise ValidationError('Each definition must have "id" and "text".')
                    if str(definition['id']) in definition_ids:
                        logger.error(f"Duplicate definition ID: {definition['id']}")
                        raise ValidationError(f'Duplicate definition ID: {definition["id"]}.')
                    definition_ids.add(str(definition['id']))
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in match options: {field.data}, error: {str(e)}")
                raise ValidationError('Options for match must be valid JSON.')

    def validate_correct(self, field):
        logger.debug(f"Validating correct field: type={self.type.data}, data={field.data}, options={self.options.data}")
        if self.type.data in ['mcq', 'tf']:
            if len(field.data) > 1:
                logger.error(f"Multiple selections for {self.type.data}: {field.data}")
                raise ValidationError('Multiple choice and true/false questions can only have one correct answer.')
            try:
                options = json.loads(self.options.data)
                valid_options = [opt.split('.')[0].strip() if '.' in opt else opt.strip() for opt in options]
                if field.data and field.data[0].strip() not in valid_options:
                    logger.error(f"Invalid correct answer for {self.type.data}: {field.data[0]}, valid_options={valid_options}")
                    raise ValidationError(f'Correct answer "{field.data[0]}" must be one of the provided options: {valid_options}.')
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in options: {self.options.data}, error: {str(e)}")
                raise ValidationError('Options must be a valid JSON array.')
        elif self.type.data == 'mrq':
            try:
                options = json.loads(self.options.data)
                valid_options = [opt.split('.')[0].strip() if '.' in opt else opt.strip() for opt in options]
                for answer in field.data:
                    answer_clean = answer.strip()
                    if answer_clean not in valid_options:
                        logger.error(f"Invalid correct answer for MRQ: {answer_clean}, valid_options={valid_options}")
                        raise ValidationError(f'Correct answer "{answer_clean}" must be one of the provided options: {valid_options}.')
                if not field.data:
                    logger.error("No correct answers selected for MRQ")
                    raise ValidationError('At least one correct answer must be selected for MRQ.')
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in options: {self.options.data}, error: {str(e)}")
                raise ValidationError('Options must be a valid JSON array.')
        elif self.type.data == 'match':
            # For match questions, validation is done on match_mappings field, not correct field
            pass

    def validate_match_mappings(self, field):
        if self.type.data == 'match':
            try:
                logger.debug(f"Validating match_mappings field: {field.data}")
                logger.debug(f"Options field: {self.options.data}")
                if not field.data:
                    logger.error("Empty match mappings")
                    raise ValidationError('Match mappings are required for match questions.')
                data = json.loads(field.data)
                if not isinstance(data, dict):
                    logger.error(f"Invalid match mappings format: {field.data}")
                    raise ValidationError('Match mappings must be a JSON object mapping term IDs to definition IDs.')
                options = json.loads(self.options.data)
                term_ids = {str(term['id']) for term in options.get('terms', [])}
                definition_ids = {str(definition['id']) for definition in options.get('definitions', [])}
                for term_id, def_id in data.items():
                    if term_id not in term_ids:
                        logger.error(f"Invalid term ID in match mappings: {term_id}")
                        raise ValidationError(f'Term ID {term_id} not found in options.terms.')
                    if def_id not in definition_ids:
                        logger.error(f"Invalid definition ID in match mappings: {def_id}")
                        raise ValidationError(f'Definition ID {def_id} not found in options.definitions.')
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in match mappings: {field.data}, error: {str(e)}")
                raise ValidationError('Match mappings must be valid JSON.')
            except TypeError:
                logger.error(f"Invalid match mappings type: {field.data}")
                raise ValidationError('Match mappings must be a valid JSON object.')

class ImportForm(FlaskForm):
    json_file = FileField('Upload JSON or ZIP File')
    overwrite = BooleanField('Overwrite Existing Tests')
    submit = SubmitField('Import')

class SimStartForm(FlaskForm):
    custom_time = IntegerField('Timer (minutes, 0 for unlimited)', default=0, validators=[NumberRange(min=0)])
    submit = SubmitField('Start Sim')