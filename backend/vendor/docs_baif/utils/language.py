import re

from langdetect import detect, DetectorFactory


# Make langdetect deterministic
DetectorFactory.seed = 0


SUPPORTED = {
    "en",
    "hi",
    "mr",
}


# ============================================================
# DEVANAGARI CHARACTER RANGE
# ============================================================

DEVANAGARI_PATTERN = re.compile(
    r"[\u0900-\u097F]"
)


# ============================================================
# COMMON HINDI WORDS
# ============================================================

HINDI_WORDS = {
    "है",
    "हैं",
    "का",
    "की",
    "के",
    "को",
    "से",
    "में",
    "पर",
    "और",
    "यह",
    "वह",
    "एक",
    "इस",
    "उस",
    "लिए",
    "किसान",
    "कृषि",
    "तकनीक",
    "भारत",
    "देश",
    "वर्ष",
    "नाम",
    "भूमिका",
    "अनुभव",
}


# ============================================================
# COMMON MARATHI WORDS
# ============================================================

MARATHI_WORDS = {
    "आहे",
    "आहेत",
    "चा",
    "ची",
    "चे",
    "ला",
    "ली",
    "ले",
    "ना",
    "ने",
    "मध्ये",
    "आणि",
    "हा",
    "ही",
    "हे",
    "एक",
    "या",
    "त्या",
    "साठी",
    "शेतकरी",
    "शेती",
    "कृषी",
    "तंत्रज्ञान",
    "भारत",
    "देश",
    "वर्ष",
    "नाव",
    "भूमिका",
    "अनुभव",
}


# ============================================================
# DETECT LANGUAGE
# ============================================================

def detect_language(text: str) -> str:
    """
    Detect Hindi, Marathi or English.

    Strategy:

    1. Empty text -> English
    2. Check Devanagari text first
       - useful for short words/cells
    3. Use common Hindi/Marathi vocabulary
    4. Use langdetect for longer text
    5. Fall back to English
    """

    if not text or not text.strip():
        return "en"

    text = text.strip()

    # --------------------------------------------------------
    # Extract Devanagari words
    # --------------------------------------------------------

    devanagari_text = " ".join(
        DEVANAGARI_PATTERN.findall(text)
    )

    has_devanagari = bool(
        DEVANAGARI_PATTERN.search(text)
    )

    # --------------------------------------------------------
    # No Devanagari
    #
    # Most likely English
    # --------------------------------------------------------

    if not has_devanagari:
        return "en"

    # --------------------------------------------------------
    # Tokenize text
    # --------------------------------------------------------

    words = re.findall(
        r"[\u0900-\u097F]+",
        text,
    )

    if not words:
        return "en"

    # --------------------------------------------------------
    # Check known Hindi / Marathi vocabulary
    # --------------------------------------------------------

    hindi_matches = sum(
        1
        for word in words
        if word in HINDI_WORDS
    )

    marathi_matches = sum(
        1
        for word in words
        if word in MARATHI_WORDS
    )

    # --------------------------------------------------------
    # Strong Marathi indication
    # --------------------------------------------------------

    if marathi_matches > hindi_matches:
        return "mr"

    # --------------------------------------------------------
    # Strong Hindi indication
    # --------------------------------------------------------

    if hindi_matches > marathi_matches:
        return "hi"

    # --------------------------------------------------------
    # Special Marathi suffix/pattern detection
    #
    # Useful for words such as:
    #
    # कृषी अधिकारी
    # क्षेत्र समन्वयक
    # शेतकरी
    # --------------------------------------------------------

    marathi_patterns = (
        "आहे",
        "आहेत",
        "मध्ये",
        "साठी",
        "णारे",
        "करी",
        "कडे",
        "मुळे",
        "पासून",
    )

    for word in words:

        if any(
            word.endswith(pattern)
            for pattern in marathi_patterns
        ):
            return "mr"

    # --------------------------------------------------------
    # If the text is very short and contains Devanagari,
    # use langdetect only as a secondary signal.
    # --------------------------------------------------------

    try:

        detected = detect(text)

        if detected == "mr":
            return "mr"

        if detected == "hi":
            return "hi"

    except Exception:
        pass

    # --------------------------------------------------------
    # For longer Devanagari text, langdetect is more reliable.
    # --------------------------------------------------------

    if len(text) >= 20:

        try:

            detected = detect(text)

            if detected in SUPPORTED:
                return detected

        except Exception:
            pass

    # --------------------------------------------------------
    # Final fallback
    #
    # Devanagari without a reliable distinction between
    # Hindi and Marathi.
    #
    # Hindi is the safer default for generic Devanagari.
    # --------------------------------------------------------

    return "hi"
