import { range } from '@/utils';

// Exported for testing purposes
export function nSpaces(n) {
    const arr = Array(n + 1);
    return `<span class="whitespace space" data-whitespace="${arr.join('&middot;')}">${arr.join(
        ' ',
    )}</span><wbr>`;
}

const MAX_SPACES = 8;
const spacesCache = range(1, MAX_SPACES + 1).map(nSpaces);

// Exported for testing purposes
export function nTabs(n) {
    const arr = Array(n + 1);
    const oneTab = `<span class="whitespace tab" data-whitespace="&#8594;">${'\t'}</span><wbr>`;
    return arr.join(oneTab);
}

const MAX_TABS = 4;
const tabsCache = range(1, MAX_TABS + 1).map(nTabs);

export function visualizeWhitespace(line) {
    const newLine = [];

    for (let i = 0; i < line.length;) {
        const start = i;
        if (line[i] === '<') {
            while (line[i] !== '>' && i < line.length) i += 1;
            newLine.push(line.slice(start, i + 1));
            i += 1;
        } else if (line[i] === ' ' || line[i] === '\t') {
            while (line[i] === line[start] && i < line.length) i += 1;

            let n = i - start;
            const cache = line[start] === ' ' ? spacesCache : tabsCache;
            while (n > 0) {
                const index = n % cache.length || cache.length;
                newLine.push(cache[index - 1]);
                n -= index;
            }
        } else {
            while (line[i] !== '<' && line[i] !== ' ' && line[i] !== '\t' && i < line.length) {
                i += 1;
            }
            newLine.push(line.slice(start, i));
        }
    }
    return newLine.join('');
}
