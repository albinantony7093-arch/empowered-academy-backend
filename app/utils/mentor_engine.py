"""
Mentor Engine — generates personalised advice based on test result.
Rule-based for now; can be upgraded to call OpenAI in Phase 2.
"""
import random

def generate_mentor_advice(score: float, accuracy: float, weak_areas: list) -> list:
    advice = []

    # Accuracy-based advice with variations
    if accuracy < 40:
        low_accuracy_advice = [
            "Your accuracy needs urgent attention. Focus on conceptual clarity before attempting more questions.",
            "Consider slowing down and reading questions more carefully to improve accuracy.",
            "Review basic concepts thoroughly before attempting practice questions.",
            "Quality over quantity - solve fewer questions but understand them completely."
        ]
        advice.append(random.choice(low_accuracy_advice))
    elif accuracy < 65:
        medium_accuracy_advice = [
            "You're answering roughly 1 in 2 correctly. Targeted revision of weak topics will quickly lift your score.",
            "Your accuracy is improving! Focus on eliminating silly mistakes to reach the next level.",
            "Practice more questions from your weak areas to boost your confidence.",
            "Try to identify patterns in the questions you're getting wrong."
        ]
        advice.append(random.choice(medium_accuracy_advice))
    else:
        high_accuracy_advice = [
            "Good accuracy! Now work on speed — timed practice will sharpen your performance further.",
            "Excellent accuracy! Challenge yourself with harder questions to maintain this level.",
            "Great job on accuracy! Focus on time management in your next practice session.",
            "Your accuracy is impressive! Try solving questions under exam conditions."
        ]
        advice.append(random.choice(high_accuracy_advice))

    # Weak areas advice with variations
    if weak_areas:
        top = weak_areas[:3]
        weak_area_advice = [
            f"Priority revision topics: {', '.join(top)}. Spend 30 minutes on each before the next test.",
            f"Focus extra attention on: {', '.join(top)}. These topics need immediate improvement.",
            f"Create a study plan targeting: {', '.join(top)}. Daily practice will help strengthen these areas.",
            f"Consider getting additional help with: {', '.join(top)}. Don't let these topics hold you back."
        ]
        advice.append(random.choice(weak_area_advice))

    # Score-based advice with variations
    if score < 100:
        low_score_advice = [
            "Review all incorrect answers immediately — understanding mistakes is the fastest way to improve.",
            "Analyze your wrong answers to identify knowledge gaps and work on them systematically.",
            "Don't get discouraged by the score. Focus on learning from each mistake.",
            "Create a mistake journal to track and review your errors regularly."
        ]
        advice.append(random.choice(low_score_advice))

    # High performance advice with variations
    if accuracy >= 80:
        excellent_advice = [
            "Excellent performance! Challenge yourself with previous years' NEET papers to consolidate your gains.",
            "Outstanding work! Try solving questions from different sources to test your knowledge.",
            "Superb accuracy! Focus on maintaining this consistency across all subjects.",
            "Great job! Now work on solving questions faster while maintaining this accuracy."
        ]
        advice.append(random.choice(excellent_advice))

    # Additional motivational and strategic advice
    strategic_advice = [
        "Remember to stay hydrated and take regular breaks during long study sessions.",
        "Try teaching concepts to others - it's a great way to reinforce your own understanding.",
        "Use the Pomodoro technique: 25 minutes of focused study followed by a 5-minute break.",
        "Create mind maps for complex topics to visualize connections between concepts.",
        "Practice deep breathing exercises before starting difficult topics to stay calm and focused."
    ]
    
    # Randomly add 1-2 strategic advice pieces
    advice.extend(random.sample(strategic_advice, random.randint(1, 2)))

    return advice


def determine_stress_level(score: float, accuracy: float) -> str:
    """
    Returns 'high_stress', 'moderate_stress', or 'low_stress'.
    Triggers Calm Corner modal on the frontend when 'high_stress'.
    """
    if accuracy < 30:
        return "high_stress"
    if accuracy < 55:
        return "moderate_stress"
    return "low_stress"
