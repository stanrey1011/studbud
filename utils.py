import json

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

def calculate_score(questions, user_answers):
    score = 0
    for question in questions:
        user_ans = user_answers.get(str(question.id))
        if question.type == 'mrq':
            correct = question.correct.split(', ') if question.correct else []
            user_ans = user_ans if isinstance(user_ans, list) else []
            if sorted(correct) == sorted(user_ans):
                score += 1
        elif question.type == 'tf':
            if str(user_ans).lower() == str(question.correct).lower():
                score += 1
        elif question.type == 'match':
            if user_ans and question.correct:
                correct_mappings = json.loads(question.correct)
                correct_count = sum(1 for term_id, def_id in user_ans.items()
                                   if correct_mappings.get(term_id) == def_id)
                score += correct_count / len(correct_mappings) if correct_mappings else 0.0
        else:
            if user_ans == question.correct:
                score += 1
    return score