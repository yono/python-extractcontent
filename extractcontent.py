#!/usr/bin/env python
# -*- encoding:utf-8 -*-
import re
import unicodedata


class ExtractContent(object):

    # convert character to entity references
    CHARREF = {
        "nbsp": " ",
        "lt": "<",
        "gt": "<",
        "amp": "&",
        "laquo": u"\xc2\xab",
        "raquo": u"\xc2\xbb",
    }

    # Default option parameters.
    default = {
        "threshold": 100,
        # threshold for score of the text
        "min_length": 80,
        # minimum length of evaluated blocks
        "decay_factor": 0.73,
        # decay factor for block score
        "continuous_factor": 1.62,
        # continuous factor for block score
        #( the larger, the harder to continue )
        "punctuation_weight": 10,
        # score weight for punctuations
        "punctuations": r"""(?is)(\343\200[\201\202]|\357\274
        [\201\214\216\237]|\.[^A-Za-z0-9]|,[^0-9]|!|\?)""",
        # punctuation characters
        "waste_expressions": r"(?i)Copyright|All Rights Reserved",
        # characteristic keywords including footer
        "debug": False,
        # if true, output block information to stdout
    }

    def __init__(self, opt=None):
        if opt != None:
            self.default.update(opt)
        self.title = ''
        self.body = ''

    # Sets option parameters to default.
    # Parameter opt is given as Dictionary.
    def set_default(self, opt):
        self.default.update(opt)

    # Analyses the given HTML text, extracts body and title.
    def analyse(self, html, opt=None):
        # flameset or redirect
        if re.search(r"""(?i)<\/frameset>|<meta\s+http-equiv\s*=\s*
                [\"']?refresh['\"]?[^>]*url""", html) != None:
            return ["", self.extract_title(html)]

        # option parameters
        if opt:
            self.default.update(opt)
            opt = self.default
        else:
            opt = self.default

        # header & title
        header = re.match(r"(?s)</head\s*>", html)
        if header != None:
            html = html[:header.end()]
            title = self.extract_title(html[0:header.start()])
        else:
            title = self.extract_title(html)

        # Google AdSense Section Target
        html = re.sub(r"""(?is)<!--\s*google_ad_section_start\(weight=
                ignore\)\s*-->.*?<!--\s*google_ad_section_end.*?-->""",
                "", html)
        if re.search(r"(?is)<!--\s*google_ad_section_start[^>]*-->",
                html) != None:
            result = re.findall(r"""(?is)<!--\s*google_ad_section_start
                    [^>]*-->.*?<!--\s*google_ad_section_end.*?-->""", html)
            html = "\n".join(result)

        # eliminate useless text
        html = self._eliminate_useless_tags(html)

        # heading tags including title
        self.title = title
        html = re.sub(r"(?s)(<h\d\s*>\s*(.*?)\s*</h\d\s*>)",
                self._estimate_title, html)

        # extract text blocks
        factor = 1.0
        continuous = 1.0
        body = ''
        score = 0
        bodylist = []
        list = \
        re.split(r"""</?(?:div|center|td)[^>]*>|<p\s*[^>]*class\s*=\s*
                [\"']?(?:posted|plugin-\w+)['\"]?[^>]*>""", html)
        for block in list:
            if self._has_only_tags(block):
                continue

            if len(body) > 0:
                continuous /= opt["continuous_factor"]

            # ignore link list block
            notlinked = self._eliminate_link(block)
            if len(notlinked) < opt["min_length"]:
                continue

            # calculate score of block
            c = (len(notlinked) + self._count_pattern(notlinked,
                opt["punctuations"]) * opt["punctuation_weight"]) * factor
            factor *= opt["decay_factor"]
            not_body_rate = self._count_pattern(block,
                opt["waste_expressions"]) + self._count_pattern(block,
                        r"amazon[a-z0-9\.\/\-\?&]+-22") / 2.0
            if not_body_rate > 0:
                c *= (0.72 ** not_body_rate)
            c1 = c * continuous
            if opt["debug"]:
                print "----- %f*%f=%f %d \n%s" %\
                    (c, continuous, c1, len(notlinked),
                            self._strip_tags(block)[0:100])

            # tread continuous blocks as cluster
            if c1 > opt["threshold"]:
                body += block + "\n"
                score += c1
                continuous = opt["continuous_factor"]
            elif c > opt["threshold"]:  # continuous block end
                bodylist.append((body, score))
                body = block + "\n"
                score = c
                continuous = opt["continuous_factor"]

        bodylist.append((body, score))
        body = reduce(lambda x, y: x if x[1] >= y[1] else y, bodylist)
        self.body = body[0]

    def as_html(self):
        return (self.body, self.title)

    def as_text(self):
        return (self._strip_tags(self.body), self.title)

    # Extract title.
    def extract_title(self, st):
        result = re.search(r"(?s)<title[^>]*>\s*(.*?)\s*</title\s*>", st)
        if result != None:
            return self._strip_tags(result.group(0))
        else:
            return ""

    # Count a pattern from text.
    def _count_pattern(self, text, pattern):
        result = re.search(pattern, text)
        if result == None:
            return 0
        else:
            return len(result.span())

    # h? タグの記述がタイトルと同じかどうか調べる
    def _estimate_title(self, match):
        striped = self._strip_tags(match.group(2))
        if len(striped) >= 3 and self.title.find(striped) != -1:
            return "<div>%s</div>" % (striped)
        else:
            return match.group(1)

    # Eliminates useless tags
    def _eliminate_useless_tags(self, html):
        # Eliminate useless symbols
        html = html.encode('utf-8')
        html = re.sub(r"""\342(?:\200[\230-\235]|\206[\220-\223]|
                \226[\240-\275]|\227[\206-\257]|\230[\205\206])""",
                "", html)
        html = html.decode('utf-8')
        # Eliminate useless html tags
        html = \
        re.sub(r"""(?is)<(script|style|select|noscript)[^>]*>.*?</\1\s*>""",
                "", html)
        html = re.sub(r"(?s)<!--.*?-->", "", html)
        html = re.sub(r"<![A-Za-z].*?>/s", "", html)
        html = re.sub(r"""(?s)<div\s[^>]*class\s*=\s*['\"]?alpslab-slide
                [\"']?[^>]*>.*?</div\s*>""", "", html)
        html = re.sub(r"""(?is)<div\s[^>]*(id|class)\s*=\s*['\"]
                ?\S*more\S*[\"']?[^>]*>""", "", html)
        return html

    # Checks if the given block has only tags without text.
    def _has_only_tags(self, st):
        st = re.sub(r"(?is)<[^>]*>", "", st)
        st = re.sub(r"&nbsp;", "", st)
        st = st.strip()
        return len(st) == 0

    # eliminate link tags
    def _eliminate_link(self, html):
        count = 0
        notlinked, count = re.subn(r"(?is)<a\s[^>]*>.*?<\/a\s*>", "", html)
        notlinked = re.sub(r"(?is)<form\s[^>]*>.*?</form\s*>", "", notlinked)
        notlinked = self._strip_tags(notlinked)
        if (len(notlinked) < 20 * count) or (self._islinklist(html)):
            return ""
        return notlinked

    # determines whether a block is link list or not
    def _islinklist(self, st):
        result = re.search(r"(?is)<(?:ul|dl|ol)(.+?)</(?:ul|dl|ol)>", st)
        if result != None:
            listpart = result.group(1)
            outside = re.sub(r"(?is)<(?:ul|dl)(.+?)</(?:ul|dl)>", "", st)
            outside = re.sub(r"(?is)<.+?>", "", outside)
            outside = re.sub(r"\s+", "", outside)
            list = re.split(r"<li[^>]*>", listpart)
            rate = self._evaluate_list(list)
            return len(outside) <= len(st) / (45 / rate)
        return False

    # estimates how much degree of link list
    def _evaluate_list(self, list):
        if len(list) == 0:
            return 1
        hit = 0
        href = re.compile("<a\s+href=(['\"]?)([^\"'\s]+)\1", re.I | re.S)
        for line in list:
            if href.search(line) != None:
                hit += 1
        return 9 * (1.0 * hit / len(list)) ** 2 + 1

    # Strips tags from html.
    def _strip_tags(self, html):
        st = re.sub(r"(?s)<.+?>", "", html)
        # Convert from wide character to ascii
        if type(st) != str:
            st = unicodedata.normalize("NFKC", st)
            st = st.encode('utf-8')
        st = re.sub(r'\342[\224\225][\200-\277]', '', st)  # keisen
        st = re.sub(r"&(.*?);", lambda x: self.CHARREF.get(x.group(1),
            x.group()), st)
        st = st.decode('utf-8')
        st = re.sub(r"[ \t]+", " ", st)
        st = re.sub(r"\n\s*", "\n", st)
        return st

if __name__ == "__main__":
    pass
