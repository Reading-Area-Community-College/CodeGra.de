/* SPDX-License-Identifier: AGPL-3.0-only */
import {
    range,
    last,
    isDecimalNumber,
    formatGrade,
    cmpOneNull,
    hashString,
    getExtension,
    waitAtLeast,
    highlightCode,
    nameOfUser,
    groupMembers,
} from '@/utils';

import * as visualize from '@/utils/visualize';

import * as highlight from 'highlightjs';

jest.useFakeTimers();

describe('utils.js', () => {
    describe('range', () => {
        it('should work for zero length', () => {
            expect(range(2, 2)).toEqual([]);
        });

        it('should work for non zero length', () => {
            expect(range(2, 10)).toEqual([2, 3, 4, 5, 6, 7, 8, 9]);
        });

        it('should work for without begin', () => {
            expect(range(10)).toEqual([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
        });
    });

    describe('last', () => {
        it('should return a reference to the last item of the array', () => {
            const lastItem = { c: 'd' };
            expect(last([{ a: 'b' }, lastItem])).toBe(lastItem);
            expect(last([{ a: 'b' }, last])).not.toBe({ c: 'd' });
        });
    });

    describe('isDecimalNumber', () => {
        it('should accept numbers', () => {
            expect(isDecimalNumber(5)).toBe(true);
            expect(isDecimalNumber(-2)).toBe(true);
            expect(isDecimalNumber(11)).toBe(true);
        });

        it('should only accept numbers and strings', () => {
            expect(isDecimalNumber({})).toBe(false);
            expect(isDecimalNumber([])).toBe(false);
            expect(isDecimalNumber(new Number(5))).toBe(true);
            expect(isDecimalNumber(new String('5'))).toBe(true);
        });

        it('should work for some strings', () => {
            expect(isDecimalNumber('hello')).toBe(false);
            expect(isDecimalNumber('0x5')).toBe(false);
            expect(isDecimalNumber('08')).toBe(false);
            expect(isDecimalNumber('1.')).toBe(false);
            expect(isDecimalNumber('0.')).toBe(false);
            expect(isDecimalNumber('.50')).toBe(false);

            expect(isDecimalNumber('0')).toBe(true);
            expect(isDecimalNumber('0.8')).toBe(true);
            expect(isDecimalNumber('-0.8')).toBe(true);
            expect(isDecimalNumber('10')).toBe(true);
            expect(isDecimalNumber('-10')).toBe(true);
            expect(isDecimalNumber('-10.10')).toBe(true);
            expect(isDecimalNumber('10.10')).toBe(true);
        });
    });

    describe('formatGrade', () => {
        it('should work with normal numbers', () => {
            expect(formatGrade(5.5)).toBe('5.50');
            expect(formatGrade(5.55555)).toBe('5.56');
            expect(formatGrade(-5.55555)).toBe('-5.56');
        });

        it('should work with string numbers', () => {
            expect(formatGrade('5.5')).toBe('5.50');
            expect(formatGrade('5.55555')).toBe('5.56');
            expect(formatGrade('-5.55555')).toBe('-5.56');
            expect(formatGrade('11')).toBe('11.00');
        });

        it('zero should return a string', () => {
            expect(typeof formatGrade('0')).toBe('string');
            expect(formatGrade('0')).toBe('0.00');
        });

        it('non floats should return null', () => {
            expect(formatGrade('NO FLOAT')).toBe(null);
            expect(formatGrade(null)).toBe(null);
        });
    });

    describe('cmpOneNull', () => {
        it('should work with all permutations', () => {
            expect(cmpOneNull(null, null)).toBe(0);
            expect(cmpOneNull('not null', null)).toBe(1);
            expect(cmpOneNull(null, 'not null')).toBe(-1);
            expect(cmpOneNull('not null', 'not null')).toBe(null);
        });
    });

    describe('hashString', () => {
        it('should be a number', () => {
            expect(typeof hashString('hello')).toBe('number');
        });

        it('should be different for different strings', () => {
            expect(hashString('hello')).not.toBe(hashString('not hello'));
        });

        it('should work for empty strings', () => {
            expect(typeof hashString('')).toBe('number');
        });
    });

    describe('getExtension', () => {
        it('should work', () => {
            expect(getExtension('noextension')).toBe(null);
            expect(getExtension('hello.c')).toBe('c');
            expect(getExtension('hello.tar.gz')).toBe('gz');
        });
    });

    describe('waitAtLeast', () => {
        const time = 5000000;
        const obj1 = {n: 1};
        const obj2 = {n: 2};

        it('should work with one Promise', async () => {
            const fn = jest.fn();
            const promise = waitAtLeast(time, Promise.resolve(obj1));
            promise.then(fn);

            jest.advanceTimersByTime(250);
            expect(fn).not.toBeCalled();

            jest.advanceTimersByTime(time - 1);
            await expect(promise).resolves.toBe(obj1);
        });

        it('should work with multiple Promises', async () => {
            const fn = jest.fn();
            const promise = waitAtLeast(time, Promise.resolve(obj1), Promise.resolve(obj2));
            promise.then(fn);

            jest.advanceTimersByTime(250);
            expect(fn).not.toBeCalled();

            jest.advanceTimersByTime(time - 1);
            await expect(promise).resolves.toEqual([obj1, obj2]);
        });

        it('longest time should be used', async () => {
            const fn = jest.fn();
            const promise = waitAtLeast(time, new Promise(resolve => setTimeout(() => resolve(obj1), time + time)));
            promise.then(fn);

            jest.advanceTimersByTime(250);
            expect(fn).not.toBeCalled();

            jest.advanceTimersByTime(time - 1);
            expect(fn).not.toBeCalled();

            jest.advanceTimersByTime(time);
            await expect(promise).resolves.toBe(obj1);
        });
    });

    describe('highlightCode', () => {
        let mockVisul;
        let mockHighlight;
        let mockGetLang;
        let i = 0;

        beforeEach(() => {
            mockVisul = jest.fn(x => x);
            visualize.visualizeWhitespace = mockVisul;

            mockHighlight = jest.fn(function() {
                return {
                    value: Array.prototype.slice.call(arguments),
                    top: `STATE${++i}`,
                };
            });
            highlight.default.highlight = mockHighlight;
            mockGetLang = jest.spyOn(highlight.default, 'getLanguage');
        });

        afterEach(() => {
            i = 0;
            mockVisul.mockRestore();
            mockHighlight.mockRestore();
            mockGetLang.mockRestore();
        });

        it('should work without a language', () => {
            const data = Array(10).fill('<a>code line</a>')
            const res = Array(10).fill('&lt;a&gt;code line&lt;/a&gt;');
            expect(highlightCode(data)).toEqual(res);
            expect(mockVisul).toHaveBeenCalledTimes(data.length);
            expect(mockGetLang).toHaveBeenCalledTimes(1);
        });

        it('should work for very large arrays', () => {
            const data = Array(100).fill('hello');
            expect(highlightCode(data, 'NOT USED!', 99)).toEqual(data);
            // Should not be called for large files
            expect(mockVisul).not.toBeCalled();
            expect(mockGetLang).not.toBeCalled();
        });

        it('should work with a language', () => {
            const code = [
                'import os',
                '',
                'with open(os.path.join("dir", "file")) as f:',
                '\tprint(f.read())',
            ];
            const result = code.map(
                (x, idx) => ['python', x, true, idx ? `STATE${idx}` : null],
            );
            expect(highlightCode(code, 'python')).toEqual(result);
            expect(mockVisul).toHaveBeenCalledTimes(code.length);
            expect(mockGetLang).toHaveBeenCalledTimes(1);
        });
    });

    describe('nameOfUser', () => {
        const obj = {};

        it('should work for normal users', () => {
            expect(nameOfUser({
                name: obj
            })).toBe(obj);
        });

        it('should work for groups', () => {
            const groupName = `The name ${Math.random()}`;
            expect(nameOfUser({
                name: obj,
                group: { name: groupName },
            })).toEqual(`Group "${groupName}"`);
        });

        it('should work for empty objects', () => {
            expect(nameOfUser(null)).toEqual('');
            expect(nameOfUser({})).toEqual('');
        });
    });

    describe('groupMembers', () => {
        it('should work for normal users', () => {
            expect(groupMembers({
                name: 'hello'
            })).toEqual([]);
        });

        it('should work for groups', () => {
            const name1 = Math.random();
            const name2 = Math.random();

            const groupName = `The name ${Math.random()}`;
            expect(groupMembers({
                name: 'HALLO',
                group: {
                    members: [
                        { name: name1 },
                        { name: name2 },
                    ],
                },
            })).toEqual([name1, name2]);
        });

        it('should work for empty objects', () => {
            expect(groupMembers(null)).toEqual([]);
            expect(groupMembers({})).toEqual([]);
        });
    });
});
