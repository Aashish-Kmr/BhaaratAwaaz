# from typing import Optional

# from faster_whisper import WhisperModel


# class Transcriber:
#     """
#     Marathi / Hindi / English speech-to-text using Faster-Whisper.

#     The important design decisions here are:
#     - small model instead of base for better Indic recognition
#     - CPU INT8 for practical Windows CPU inference
#     - VAD to remove silent/non-speech sections
#     - condition_on_previous_text=False to reduce hallucination propagation
#     - confidence / repetition filtering
#     """

#     def __init__(self):
#         print("Loading Faster-Whisper model: small")

#         self.model = WhisperModel(
#             "small",
#             device="cpu",
#             compute_type="int8",
#             cpu_threads=11,
#             num_workers=1,
#         )

#         print("Faster-Whisper ready.")

#     def transcribe(
#         self,
#         audio_path: str,
#         language: str = "mr",
#     ):

#         print(f"Transcribing: {audio_path}")
#         print(f"Whisper language: {language}")

#         segments, info = self.model.transcribe(
#             audio_path,

#             # Explicit language prevents Whisper from trying
#             # to identify garbage as another language.
#             language=language,

#             # Better decoding quality.
#             beam_size=5,
#             best_of=5,

#             # Very important for this video.
#             # Prevents previous hallucinations from contaminating
#             # later segments.
#             condition_on_previous_text=False,

#             # Voice Activity Detection.
#             # This is the major fix for the huge fake subtitles.
#             vad_filter=True,
#             vad_parameters={
#                 "threshold": 0.45,
#                 "min_silence_duration_ms": 500,
#                 "speech_pad_ms": 250,
#             },

#             # Better timestamp information.
#             word_timestamps=True,

#             # Hallucination / low-confidence protection.
#             no_speech_threshold=0.60,
#             log_prob_threshold=-1.0,
#             compression_ratio_threshold=2.4,

#             # Deterministic decoding.
#             temperature=0.0,
#         )

#         result = []

#         for segment in segments:

#             text = segment.text.strip()

#             # Reject obvious character-level repetition
#             if len(text) >= 20:

#                 compact = (
#                     text
#                     .replace(" ", "")
#                     .replace("।", "")
#                     .replace(".", "")
#                     .replace(",", "")
#                 )

#                 if compact:
#                     unique_chars = len(set(compact))
#                     repetition_ratio = (
#                         unique_chars / len(compact)
#                     )

#                     if repetition_ratio < 0.08:
#                         print(
#                             "Skipping character-level "
#                             "hallucination:",
#                             text,
#                         )
#                         continue

#             if not text:
#                 continue

#             start = float(segment.start)
#             end = float(segment.end)

#             # Ignore punctuation-only hallucinations.
#             cleaned = text.replace(
#                 " ",
#                 "",
#             )

#             punctuation_only = all(
#                 char in "।॥.,!?;:!?-—…|"
#                 for char in cleaned
#             )

#             if punctuation_only:
#                 print(
#                     f"Skipping punctuation hallucination: "
#                     f"[{start:.2f} -> {end:.2f}] {text}"
#                 )
#                 continue

#             # Reject obvious repeated-character hallucinations.
#             words = text.split()

#             if len(words) >= 8:
#                 unique_words = len(
#                     set(words)
#                 )

#                 repetition_ratio = (
#                     unique_words / len(words)
#                 )

#                 if repetition_ratio < 0.20:
#                     print(
#                         f"Skipping repetitive hallucination: "
#                         f"[{start:.2f} -> {end:.2f}] {text}"
#                     )
#                     continue

#             # Ignore extremely short fragments.
#             if end - start < 0.25:
#                 continue

#             result.append(
#                 {
#                     "start": start,
#                     "end": end,
#                     "text": text,
#                 }
#             )

#             print(
#                 f"[{start:.2f} -> {end:.2f}] {text}"
#             )

#         print(
#             f"Transcription complete: "
#             f"{len(result)} segments"
#         )

#         print(
#             f"Detected language: "
#             f"{info.language} "
#             f"({info.language_probability:.2f})"
#         )

#         return {
#             "segments": result,
#             "language": info.language,
#             "language_probability": float(
#                 info.language_probability
#             ),
#         }


# # ---------------------------------------------------------
# # Singleton
# # ---------------------------------------------------------

# _transcriber: Optional[Transcriber] = None


# def get_transcriber() -> Transcriber:

#     global _transcriber

#     if _transcriber is None:
#         _transcriber = Transcriber()

#     return _transcriber


# def transcribe_audio(
#     audio_path: str,
#     language: str = "mr",
# ):
#     """
#     Backward-compatible helper.
#     """

#     return get_transcriber().transcribe(
#         audio_path,
#         language,
#     )




























from typing import Optional

from faster_whisper import (
    WhisperModel,
    BatchedInferencePipeline,
)


class Transcriber:

    # Upstream used "small". Raised to "medium" for noticeably better
    # Marathi/Hindi recognition -- measured ~2.6x slower on CPU (roughly
    # 0.67x realtime vs 1.73x), which is the deliberate trade. It also
    # means this pipeline now shares the audio pipeline's model, so the
    # build no longer has to ship faster-whisper-small at all.
    MODEL_SIZE = "medium"

    def __init__(self):
        print(f"Loading Faster-Whisper model: {self.MODEL_SIZE}")

        self.model = WhisperModel(
            self.MODEL_SIZE,
            device="cpu",
            compute_type="int8",
            cpu_threads=11,
            num_workers=1,
        )

        # Batched inference improves throughput on supported
        # Faster-Whisper versions.
        self.batched_model = BatchedInferencePipeline(
            model=self.model
        )

        print("Faster-Whisper ready.")

    @staticmethod
    def _is_bad_segment(text: str) -> bool:
        text = text.strip()

        if not text:
            return True

        cleaned = (
            text.replace(" ", "")
            .replace("।", "")
            .replace(".", "")
            .replace(",", "")
        )

        if not cleaned:
            return True

        # punctuation-only / symbol-only output
        if all(
            c in "।॥.,!?;:-—…|"
            for c in cleaned
        ):
            return True

        words = text.split()

        # Repeated-word hallucinations.
        #
        # The original threshold was 0.70 of the whole segment, which is
        # too lax to catch a real case seen in practice: a 40-word segment
        # ending in "लिए" x22 scores 0.55 and sailed through. Lowered to
        # 0.50.
        if len(words) >= 8:
            counts = {}

            for word in words:
                counts[word] = counts.get(word, 0) + 1

            if max(counts.values()) / len(words) > 0.50:
                return True

        # Overall frequency is the wrong shape for this failure anyway: a
        # loop is a *consecutive* run ("लिए लिए लिए लिए ..."), and a long
        # enough run is damning even when a long preamble dilutes its share
        # of the segment. Catch that directly.
        run = best_run = 1
        for previous, current in zip(words, words[1:]):
            run = run + 1 if current == previous else 1
            best_run = max(best_run, run)

        if best_run >= 5:
            return True

        # Repeated-character hallucinations
        if len(cleaned) >= 20:
            if len(set(cleaned)) / len(cleaned) < 0.08:
                return True

        return False

    def transcribe(
        self,
        audio_path: str,
        language: str = "mr",
    ):
        print(f"Transcribing: {audio_path}")
        print(f"Whisper language: {language}")

        segments, info = self.batched_model.transcribe(
            audio_path,
            language=language,

            # Keep accuracy high.
            beam_size=5,

            # Prevent hallucination propagation.
            condition_on_previous_text=False,

            # Softer VAD than before to avoid missing speech.
            vad_filter=True,
            vad_parameters={
                "threshold": 0.35,
                "neg_threshold": 0.20,
                "min_speech_duration_ms": 200,
                "min_silence_duration_ms": 1000,
                "speech_pad_ms": 400,
            },

            # Segment timestamps are enough for SRT.
            word_timestamps=False,

            # Temperature *ladder*, not a single value. compression_ratio
            # and log_prob thresholds below detect a degenerate decode, but
            # the only way Whisper can act on that is to re-decode at a
            # higher temperature. Pinning temperature=0.0 (as this did)
            # leaves it nothing to fall back to, so a detected repetition
            # loop was kept rather than retried. Measured on a 9m41s
            # Marathi file: worst single-word repetition 0.15 -> 0.11, and
            # ~12% faster overall, because degenerate decodes stop running
            # to max length.
            temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],

            # Belt and braces against the same failure: forbid any 3-gram
            # from repeating, and mildly penalise repeated tokens.
            no_repeat_ngram_size=3,
            repetition_penalty=1.15,

            no_speech_threshold=0.60,
            log_prob_threshold=-1.0,
            compression_ratio_threshold=2.4,

            # Batch size: start conservative on CPU.
            batch_size=8,
        )

        result = []

        for segment in segments:
            text = segment.text.strip()

            start = float(segment.start)
            end = float(segment.end)

            if self._is_bad_segment(text):
                print(
                    f"Skipping hallucination: "
                    f"[{start:.2f} -> {end:.2f}] {text}"
                )
                continue

            if end - start < 0.25:
                continue

            result.append(
                {
                    "start": start,
                    "end": end,
                    "text": text,
                }
            )

            print(
                f"[{start:.2f} -> {end:.2f}] {text}"
            )

        print(
            f"Transcription complete: "
            f"{len(result)} segments"
        )

        print(
            f"Detected language: "
            f"{info.language} "
            f"({info.language_probability:.2f})"
        )

        return {
            "segments": result,
            "language": info.language,
            "language_probability": float(
                info.language_probability
            ),
        }


_transcriber: Optional[Transcriber] = None


def get_transcriber() -> Transcriber:
    global _transcriber

    if _transcriber is None:
        _transcriber = Transcriber()

    return _transcriber


def transcribe_audio(
    audio_path: str,
    language: str = "mr",
):
    return get_transcriber().transcribe(
        audio_path,
        language,
    )