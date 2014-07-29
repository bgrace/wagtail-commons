__author__ = 'bgrace'

class Token(object):

    def __init__(self, contents):
        self.contents = contents


class DocumentDelimiterToken(Token):
    pass


class DocumentTypeToken(Token):
    pass


class DocumentAntecedentToken(Token):
    pass


class DocumentBody(Token):
    pass


class Tokenizer(object):

    """
    document = doc_delimiter newline body {newline doc_delimiter whitespace symbol newline body};
    doc_delimiter = "---";
    newline = "\n";
    whitespace = " " | "\t";
    symbol = '@', alphanumeric | '!', alphanumeric;
    alphanumeric = ? a-aA-Z ?, ? a-aA-Z0-9 ?
    body = {line} | delimiter, newline;
    line = {printable_character} newline;
    """

    delimiter = "---"

    def __init__(self, readable):
        self.input = readable

        self.tokens = []

    def tokenize_input(self):
        for line in self.input.readline():
            self.tokens.append(self.tokenize_line(line))

    def tokenize_line(self, line):
        if line.startswith("---"):
            # TODO I stopped working right here, finishing this block!
            pass