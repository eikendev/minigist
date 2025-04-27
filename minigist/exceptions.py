class MinigistError(Exception):
    pass


class ConfigError(MinigistError):
    pass


class MinifluxApiError(MinigistError):
    pass


class SummarizationError(MinigistError):
    pass


class ArticleFetchError(SummarizationError):
    pass


class AIServiceError(SummarizationError):
    pass
