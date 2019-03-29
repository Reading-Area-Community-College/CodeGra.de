/* SPDX-License-Identifier: AGPL-3.0-only */
import moment from 'moment';
import { getLanguage, highlight } from 'highlightjs';
import { visualizeWhitespace } from './visualize';

const reUnescapedHtml = /[&<>"'`]/g;
const reHasUnescapedHtml = RegExp(reUnescapedHtml.source);
/** Used to map characters to HTML entities. */
const htmlEscapes = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
    '`': '&#96;',
};
export function htmlEscape(inputString) {
    const string = typeof inputString === 'string' ? inputString : `${inputString}`;
    if (string && reHasUnescapedHtml.test(string)) {
        return string.replace(reUnescapedHtml, ent => htmlEscapes[ent]);
    }
    return string;
}

export function formatGrade(grade) {
    const g = parseFloat(grade);
    return Number.isNaN(g) ? null : g.toFixed(2);
}

export function cmpOneNull(first, second) {
    if (first == null && second == null) {
        return 0;
    } else if (first == null) {
        return -1;
    } else if (second == null) {
        return 1;
    }
    return null;
}

export function cmpNoCase(first, second) {
    return first.toLocaleLowerCase().localeCompare(second.toLocaleLowerCase());
}

/**
 * Parse the given value as a boolean.
 * If it is a boolean return it, if it is 'false' or 'true' convert
 * that to its correct boolean value, otherwise return `dflt`.
 */
export function parseBool(value, dflt = true) {
    if (typeof value === 'boolean') return value;
    else if (value === 'false') return false;
    else if (value === 'true') return true;

    return dflt;
}

export function formatDate(date) {
    return moment
        .utc(date, moment.ISO_8601)
        .local()
        .format('YYYY-MM-DDTHH:mm');
}

export function readableFormatDate(date) {
    return moment
        .utc(date, moment.ISO_8601)
        .local()
        .format('YYYY-MM-DD HH:mm');
}

export function convertToUTC(timeStr) {
    return moment(timeStr, moment.ISO_8601)
        .utc()
        .format('YYYY-MM-DDTHH:mm');
}

export function parseWarningHeader(warningStr) {
    const arr = warningStr.split(' ');

    const code = parseFloat(arr[0]);
    const agent = arr[1];
    const text = arr
        .slice(2)
        .join(' ')
        .replace(/\\"/g, '"')
        .slice(1, -1);

    return { code, agent, text };
}

export function waitAtLeast(time, ...promises) {
    const timeout = new Promise(resolve => setTimeout(resolve, time));

    return Promise.all([timeout, ...promises]).then(vals => {
        if (promises.length === 1) {
            return vals[1];
        } else {
            return vals.slice(1);
        }
    });
}

export function getExtension(name) {
    const fileParts = name.split('.');
    return fileParts.length > 1 ? fileParts[fileParts.length - 1] : null;
}

export function last(arr) {
    return arr[arr.length - 1];
}

export function range(start, end) {
    const len = end - start;
    const res = Array(len);
    for (let i = 0; i < len; ++i) {
        res[i] = start + i;
    }
    return res;
}

export function isDecimalNumber(val) {
    if (typeof val === 'number' || val instanceof Number) return true;
    else if (!(typeof val === 'string' || val instanceof String)) return false;

    let res = /^-?[1-9]\d*$/.test(val);
    res = res || /^0$/.test(val);
    res = res || /^-?[1-9]\d*\.\d+$/.test(val);
    res = res || /^-?0\.\d+$/.test(val);
    return res;
}

export function hashString(str) {
    let hash = 0;
    if (str.length === 0) return hash;

    for (let i = 0; i < str.length; i++) {
        const character = str.charCodeAt(i);
        hash = (hash << 5) - hash + character;
        hash &= hash; // Convert to 32bit integer
    }
    return Math.abs(hash << 0);
}

export function getOtherAssignmentPlagiarismDesc(item, index) {
    const assig = item.assignments[index];
    if (assig && assig.course.virtual) {
        return 'This submission was uploaded during running as part of an archive of old submissions.';
    }

    let desc = `This assignment was submitted to the assignment "${
        item.assignments[index].name
    }" of "${item.assignments[index].course.name}"`;

    if (item.submissions != null) {
        const date = moment
            .utc(item.submissions[index].created_at, moment.ISO_8601)
            .local()
            .format('YYYY-MM-DD');
        desc = `${desc} on ${date}`;
    }

    return desc;
}

export function nameOfUser(user) {
    if (!user) return '';
    else if (user.group) return `Group "${user.group.name}"`;
    else return user.name || '';
}

export function groupMembers(user) {
    if (!user || !user.group) return [];
    return user.group.members.map(nameOfUser);
}

export function highlightCode(sourceArr, language, maxLen = 5000) {
    if (sourceArr.length > maxLen) {
        return sourceArr.map(htmlEscape);
    }

    if (getLanguage(language) === undefined) {
        return sourceArr.map(htmlEscape).map(visualizeWhitespace);
    }

    let state = null;
    return sourceArr.map(line => {
        const { top, value } = highlight(language, line, true, state);

        state = top;
        return visualizeWhitespace(value);
    });
}

export function loadCodeAndFeedback(http, fileId) {
    return Promise.all([
        http.get(`/api/v1/code/${fileId}`),
        http.get(`/api/v1/code/${fileId}?type=feedback`).catch(() => ({
            data: {},
        })),
    ]).then(
        ([{ data: code }, { data: feedback }]) => ({ code, feedback }),
        ({ response: { data: { message } } }) => {
            throw message;
        },
    );
}

export function enumerateItems(list) {
    if (list.length === 1) {
        return list[0];
    } else if (list.length === 2) {
        return `${list[0]} and ${list[1]}`;
    } else {
        const butLast = list.slice(0, -1);
        return `${butLast.join(',')}, and ${list[list.length - 1]}`;
    }
}
