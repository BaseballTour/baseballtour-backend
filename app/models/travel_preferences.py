from enum import Enum


class PreferredCategory(str, Enum):
    FOOD = "FOOD"
    ACTIVITY = "ACTIVITY"
    SHOPPING = "SHOPPING"
    EXPERIENCE = "EXPERIENCE"
    RELAXATION = "RELAXATION"
    HISTORY = "HISTORY"
    NATURE = "NATURE"
    CULTURE = "CULTURE"


class ScheduleDensity(str, Enum):
    LIGHT = "LIGHT"
    MODERATE = "MODERATE"
    DENSE = "DENSE"
