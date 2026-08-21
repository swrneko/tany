from dataclasses import dataclass

# Every prompt tells the model to answer in the language of the transcript.
# The alternative -- a prompt set per interface locale -- would summarise a
# Russian meeting in English because the reader happened to switch the UI.
LANGUAGE_RULE = "Write your answer in the same language as the transcript."


@dataclass(frozen=True)
class BuiltinPreset:
    key: str
    name: str
    description: str
    system_prompt: str
    user_template: str
    temperature: float


BUILTIN_PRESETS: tuple[BuiltinPreset, ...] = (
    BuiltinPreset(
        key="brief",
        name="Brief summary",
        description="A few sentences on what this was about",
        system_prompt=(
            "You summarise transcripts. Be accurate and plain. Never invent facts "
            f"that are not in the transcript. {LANGUAGE_RULE}"
        ),
        user_template=(
            "Summarise the following transcript in three to five sentences.\n\n{transcript}"
        ),
        temperature=0.2,
    ),
    BuiltinPreset(
        key="detailed",
        name="Detailed notes by topic",
        description="Sectioned notes covering everything discussed",
        system_prompt=(
            "You turn transcripts into structured notes. Keep every topic that was "
            f"actually discussed and invent nothing. {LANGUAGE_RULE}"
        ),
        user_template=(
            "Turn the transcript below into detailed notes. Group them under headings "
            "by topic, in the order the topics came up.\n\n{transcript}"
        ),
        temperature=0.3,
    ),
    BuiltinPreset(
        key="actions",
        name="Decisions and action items",
        description="What was decided and who has to do what",
        system_prompt=(
            "You extract decisions and commitments from transcripts. If nobody was "
            "named as responsible, say so rather than guessing a name. "
            f"{LANGUAGE_RULE}"
        ),
        user_template=(
            "From the transcript below, list the decisions that were made and the "
            "action items, with the person responsible and any deadline mentioned. "
            "If there are none, say so.\n\n{transcript}"
        ),
        temperature=0.1,
    ),
    BuiltinPreset(
        key="bullets",
        name="Key points",
        description="The substance as a flat list of bullets",
        system_prompt=(
            f"You reduce transcripts to their key points. One idea per bullet. {LANGUAGE_RULE}"
        ),
        user_template="List the key points of the transcript below as bullets.\n\n{transcript}",
        temperature=0.2,
    ),
    BuiltinPreset(
        key="minutes",
        name="Meeting minutes",
        description="Participants, agenda, discussion, outcomes",
        system_prompt=(
            "You write meeting minutes from transcripts. Use only what was said. "
            f"{LANGUAGE_RULE}"
        ),
        user_template=(
            "Write minutes for the meeting below, covering the participants you can "
            "identify, what was discussed, and what came out of it.\n\n{transcript}"
        ),
        temperature=0.2,
    ),
    BuiltinPreset(
        key="custom",
        name="Blank",
        description="A starting point for your own instructions",
        system_prompt=f"You are a careful assistant. {LANGUAGE_RULE}",
        user_template="{transcript}",
        temperature=0.3,
    ),
)
