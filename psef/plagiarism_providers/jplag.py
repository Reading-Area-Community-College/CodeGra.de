"""This module implements the provider for the JPlag plagiarism checker.

This provider only works with the codegrade fork of JPlag as other versions do
not output the needed csv file.

:license: AGPLv3, see LICENSE for details.
"""

import typing as t

import psef
import psef.helpers
import psef.plagiarism as plag

_SUPPORTED_LANGS = {
    "Python 3": "python3",
    "C/C++": "c/c++",
    "Java 1": "java11",
    "Java 2": "java12",
    "Java 5": "java15dm",
    "Java 7": "java17",
    "Java 8": "java15",
    "C# 1.2": "c#-1.2",
    "Chars": "char",
    "Text": "text",
    "Scheme": "scheme",
}
"""Supported languages for JPlag and their human readable equivalent."""


class JPlag(plag.PlagiarismProvider):
    """This class implements the JPlag plagiarism provider.
    """

    def __init__(self) -> None:
        self.lang: t.Optional[str] = None
        self.suffixes: t.Optional[str] = None
        self.simil: int = 25

    @property
    def matches_output(self) -> str:
        """The path were the result csv is placed.

        :returns: The specified path
        """
        return 'computer_matches.csv'

    @staticmethod
    def get_options() -> t.Sequence[plag.Option]:
        """Get all possible options for JPlag.

        :returns: The possible options.
        """
        return [
            plag.Option(
                "lang",
                "Language",
                "The language used to parse the files from the student",
                plag.OptionTypes.singleselect,
                True,
                list(_SUPPORTED_LANGS.keys()),
            ),
            plag.Option(
                "suffixes",
                "Suffixes to include",
                (
                    "A comma separated list of suffixes. A file is only parsed"
                    " if it ends with one of the given suffixes exactly, no"
                    " regex is supported. If this value is left empty suitable"
                    " suffixes will be selected for the selected language."
                ),
                plag.OptionTypes.strvalue,
                False,
                None,
                placeholder='.xxx, .yyy',
            ),
            plag.Option(
                "simil",
                "Minimal similarity",
                (
                    "The minimal average similarity needed before a pair is "
                    "considered plagiarism. If this is set to 100 both "
                    "assignments need to be completely the same, when set to"
                    " 50 both submissions need to be 50% the same, or one 25%"
                    " and the other 75%. The default is 25"
                ),
                plag.OptionTypes.numbervalue,
                False,
                None,
                placeholder=25,
            ),
        ]

    def _set_provider_values(self, values: t.Dict[str, psef.helpers.JSONType]
                             ) -> None:
        """Set the options for JPlag.

        :param values: The values to be set.
        :returns: Nothing.
        """
        self.lang = _SUPPORTED_LANGS[str(values['lang'])]
        if 'suffixes' in values:
            self.suffixes = str(values['suffixes'])
        if 'simil' in values:
            assert isinstance(values['simil'], (int, float))
            self.simil = int(values['simil'])

    def get_program_call(self) -> t.List[str]:
        """Get the program call for JPlag.

        :returns: A list as that can be used with
            :func:`subprocess.check_output` to run JPlag.
        """
        java = psef.app.config['JAVA_PATH']
        jar = psef.app.config['JPLAG_JAR']
        assert self.lang is not None

        # yapf: disable
        res = [
            java,
            '-jar', jar,
            '{ restored_dir }',
            '-l', self.lang,
            '-s',
            '-r', '{ result_dir }',
            '-m', f'{self.simil}%',
        ]
        # yapf: enable

        if self.suffixes is not None:
            res.extend(['-p', self.suffixes])

        return res
