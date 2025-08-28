document.addEventListener('DOMContentLoaded', () => {
    const questions = document.querySelectorAll('.question');
    if (mode === 'study') {
        questions.forEach(q => {
            q.querySelector('.reveal').addEventListener('click', () => {
                const feedback = q.querySelector('.feedback');
                feedback.innerHTML = `Correct: ${q.dataset.correct}<br>Explanation: ${q.dataset.explanation}`;
                feedback.classList.remove('d-none');
            });
            if (q.querySelector('.flashcard')) {
                q.querySelector('.front').addEventListener('click', () => q.querySelector('.back').classList.remove('d-none'));
            }
        });
    } else if (mode === 'test') {
        let time = 3600; // 1 hour example; adjust
        const timerInterval = setInterval(() => {
            time--;
            document.getElementById('timer').textContent = `Time left: ${Math.floor(time/60)}:${time%60}`;
            if (time <= 0) {
                clearInterval(timerInterval);
                submitTest();
            }
        }, 1000);

        document.getElementById('submit-test').addEventListener('click', submitTest);

        function submitTest() {
            const answers = {};
            let score = 0;
            questions.forEach(q => {
                const id = q.dataset.id;
                const selected = q.querySelector('input:checked') ? q.querySelector('input:checked').value : null;
                answers[id] = selected;
                if (selected === q.dataset.correct) score += 1;
            });
            score = (score / questions.length * 100).toFixed(2);
            fetch(`/user/quiz/${testId}/${mode}`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({score, answers})
            }).then(res => res.json()).then(data => {
                alert(`Test submitted! Score: ${score}%`);
                window.location.href = '/user/history';
            });
        }
    }
});