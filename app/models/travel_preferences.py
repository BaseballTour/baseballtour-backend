from enum import Enum


class TravelStyle(str, Enum):
    RELAXED = "RELAXED"
    BALANCED = "BALANCED"
    EXPLORER = "EXPLORER"


class ScheduleDensity(str, Enum):
    LIGHT = "LIGHT"
    MODERATE = "MODERATE"
    DENSE = "DENSE"
