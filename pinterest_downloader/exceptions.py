class PinterestError(Exception):
    pass


class PinNotFoundError(PinterestError):
    pass


class UserNotFoundError(PinterestError):
    pass


class BoardNotFoundError(PinterestError):
    pass


class SearchError(PinterestError):
    pass


class InvalidURLError(PinterestError):
    pass
  
