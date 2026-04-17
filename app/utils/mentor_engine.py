"""
Mentor Engine — generates personalised advice based on test result.
Rule-based for now; can be upgraded to call OpenAI in Phase 2.
"""

def generate_mentor_advice(score: float, accuracy: float, weak_areas: list) -> list:
    advice = []

    if accuracy < 40:
        advice.append("Your accuracy needs urgent attention. Focus on conceptual clarity before attempting more questions.")
    elif accuracy < 65:
        advice.append("You're answering roughly 1 in 2 correctly. Targeted revision of weak topics will quickly lift your score.")
    else:
        advice.append("Good accuracy! Now work on speed — timed practice will sharpen your performance further.")

    if weak_areas:
        top = weak_areas[:3]
        advice.append(f"Priority revision topics: {', '.join(top)}. Spend 30 minutes on each before the next test.")

    if score < 100:
        advice.append("Review all incorrect answers immediately — understanding mistakes is the fastest way to improve.")

    if accuracy >= 80:
        advice.append("Excellent performance! Challenge yourself with previous years' NEET papers to consolidate your gains.")

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
