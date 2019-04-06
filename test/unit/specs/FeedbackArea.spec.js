/* SPDX-License-Identifier: AGPL-3.0-only */
import FeedbackArea from '@/components/FeedbackArea';
import { shallowMount, createLocalVue } from '@vue/test-utils';
import VueRouter from 'vue-router';
import Vuex from 'vuex';
import BootstrapVue from 'bootstrap-vue'

jest.mock('axios');

const localVue = createLocalVue();
localVue.use(Vuex);
localVue.use(BootstrapVue);

const snippets = [{
    id: 0, key: 'snippet', value: 'snippet expanded text',
}, {
    id: 1, key: 'snippets2', value: 'WOW NOG EEN SNIPPET',
}, {
    id: 2, key: 'snippets3', value: 'WOW NOG EEN SNIPPET2',
}];

describe('FeedbackArea.vue', () => {
    let store;
    let wrapper;
    let comp;
    let mockRefresh;
    let mockAdd;
    let mockUpdate;
    let mockPut;
    let mockPatch;
    let updateSelection;

    function makeInstance(propsData = null) {
        wrapper = shallowMount(FeedbackArea, {
            store,
            localVue,
            methods: {
                $hasPermission() { return true; },
            },
            mocks: {
                $http: {
                    put: mockPut,
                    patch: mockPatch,
                },
            },
            propsData: Object.assign({
                line: 0,
                feedback: '',
                fileId: 0,
                editing: true,
                totalAmountLines: 100,
                assignment: {
                    course: {
                        id: 10,
                        snippets: [],
                    },
                },
            }, propsData),
        });
        wrapper.vm.$refs.field = {
            focus: jest.fn(),
            selectionStart: 0,
            selectionEnd: 0,
        };

        comp = wrapper.vm;
    }

    beforeEach(() => {
        mockRefresh = jest.fn(() => Promise.resolve(true));
        mockAdd = jest.fn();
        mockUpdate = jest.fn();
        mockPut = jest.fn(() => Promise.resolve(true));
        mockPatch = jest.fn(() => Promise.resolve(true));

        updateSelection = () => {
            comp.$refs.field.selectionStart = comp.internalFeedback.length || 0;
            comp.$refs.field.selectionEnd = comp.internalFeedback.length || 0;
        };

        store = new Vuex.Store({
            modules: {
                user: {
                    state: {
                        snippets,
                    },
                    getters: {
                        snippets: () => snippets.reduce((accum, val) => {
                            accum[val.key] = val;
                            return accum;
                        }, {}),
                        findSnippetsByPrefix: () => (prefix) => {
                            return snippets.filter(s => s.key.startsWith(prefix));
                        },
                    },
                    actions: {
                        maybeRefreshSnippets: mockRefresh,
                        addSnippet: mockAdd,
                        updateSnippet: mockUpdate,
                    },
                    namespaced: true,
                },
            },
        });


        makeInstance({ canUseSnippets: true });
    });

    it('should not be null', () => {
        expect(comp).not.toBe(null);
    });

    describe('expandSnippet', () => {
        const event = { preventDefault: () => {} };

        it('should do nothing if the user can\'t use snippets', () => {
            makeInstance({ canUseSnippets: false });

            const snippetK = snippets[0].key;
            comp.canUseSnippets = false;
            comp.internalFeedback = snippetK;
            comp.maybeSelectNextSnippet();
            expect(comp.internalFeedback).toBe(snippetK);
        });

        it('should do nothing if some text is selected', () => {
            const snippetK = snippets[0].key;
            comp.$refs.field = { selectionStart: 0, selectionEnd: 2 };
            comp.internalFeedback = snippetK;
            comp.maybeSelectNextSnippet();
            expect(comp.internalFeedback).toBe(snippetK);
        });

        it('should do nothing if the last word is not a snippet', () => {
            let values = [
                'nonexisting',
                'this snippet is nonexisting',
                `multiline text

                this snippet is nonexisting`,
                'nonexisting-snippet',
            ];
            let field = {};
            comp.$refs.field = field;

            for (let value of values) {
                field.selectionStart = value.length;
                field.selectionEnd = value.length;
                comp.internalFeedback = value;
                comp.maybeSelectNextSnippet();
                expect(comp.internalFeedback).toBe(value);
                expect(comp.possibleSnippets.length).toBe(0);
            }
        });

        it('should expand the last word if it is a snippet', async () => {
            let values = [
                'snippet',
                'this is a snippet',
                `multiline text

                ending in a snippet`,
            ];

            for (let value of values) {
                localVue.set(comp, 'internalFeedback', value);
                updateSelection();
                comp.updatePossibleSnippets({ event: { key: 't' } });

                expect(comp.possibleSnippets.length).toBe(3);

                updateSelection();
                comp.maybeSelectNextSnippet();
                await comp.$nextTick();
                expect(comp.internalFeedback).toBe(
                    value.replace(/snippet$/, snippets[0].value),
                );

                updateSelection();
                comp.maybeSelectNextSnippet();
                await comp.$nextTick();
                expect(comp.internalFeedback).toBe(
                    value.replace(/snippet$/, snippets[1].value),
                );

                updateSelection();
                comp.maybeSelectNextSnippet();
                await comp.$nextTick();
                expect(comp.internalFeedback).toBe(
                    value.replace(/snippet$/, snippets[2].value),
                );

                updateSelection();
                comp.maybeSelectNextSnippet();
                expect(comp.snippetIndexSelected).toBe(null);
                await comp.$nextTick();
                await comp.$nextTick();
                expect(comp.internalFeedback).toBe(value);
            }
        });

        it('should expand to all snippets with no input', async () => {
            comp.internalFeedback = '';
            updateSelection();
            comp.maybeSelectNextSnippet();
            await comp.$nextTick();
            expect(comp.possibleSnippets.length).toBe(3);

            // Notice space at the end
            localVue.set(comp, 'internalFeedback', 'snippets2 ');
            updateSelection();
            comp.maybeSelectNextSnippet();
            expect(comp.possibleSnippets.length).toBe(3);
        });

        it('should be possible to filter more', () => {
            localVue.set(comp, 'internalFeedback', 'a snippet');
            updateSelection();
            comp.updatePossibleSnippets({ event: { key: 't' } });
            expect(comp.possibleSnippets.length).toBe(3);

            localVue.set(comp, 'internalFeedback', comp.internalFeedback + 's');
            updateSelection();
            comp.updatePossibleSnippets({ event: { key: 's' } });
            expect(comp.possibleSnippets.length).toBe(2);
            expect(comp.possibleSnippets.map(a => a.key)).toEqual(['snippets2', 'snippets3']);
            expect(comp.snippetIndexSelected).toBe(null);
        });
    });

    describe('addSnippet', () => {
        it('should fail if the snippet key is invalid', async () => {
            let caught = 0;

            comp.snippetKey = 'key with spaces';
            comp.internalFeedback = 'feedback';
            try {
                await comp.addSnippet();
            } catch (e) {
                caught += 1;
                expect(e.message).toMatch('spaces');
            };

            comp.snippetKey = '';
            try {
                await comp.addSnippet();
            } catch (e) {
                caught += 1;
                expect(e.message).toMatch('empty');
            }

            expect(caught).toBe(2);
        });

        it('should fail if the feedback is empty', async () => {
            let caught = 0;

            comp.snippetKey = 'key';
            comp.internalFeedback = '';
            try {
                await comp.addSnippet();
            } catch (e) {
                caught += 1;
            }
            expect(caught).toBe(1);
        });

        it('should update a snippet if the key already exists', async () => {
            comp.snippetKey = 'snippet';
            comp.internalFeedback = 'new value';
            await comp.addSnippet().then(comp.afterAddSnippet);
            expect(mockAdd).toBeCalledTimes(0);
            expect(mockPut).toBeCalledTimes(0);
            expect(mockUpdate).toBeCalledTimes(1);
            expect(mockPatch).toBeCalledTimes(1);
        });

        it('should add a new snippet if the key doesn\'t exist', async () => {
            comp.snippetKey = 'new_snippet';
            comp.internalFeedback = 'new value';
            await comp.addSnippet().then(comp.afterAddSnippet);
            expect(mockAdd).toBeCalledTimes(1);
            expect(mockPut).toBeCalledTimes(1);
            expect(mockUpdate).toBeCalledTimes(0);
            expect(mockPatch).toBeCalledTimes(0);
        });
    });

    describe('findSnippet', () => {
        beforeEach(() => {
            comp.$refs.snippetDialog = { show: false };
        });

        it('should do nothing if the field already has a value', () => {
            comp.snippetKey = 'new_snippet';
            comp.internalFeedback = snippets[0].value;
            comp.findSnippet();
            expect(comp.snippetKey).toBe('new_snippet');
        });

        it('should do nothing if the snippet dialog is visible', () => {
            comp.showSnippetDialog = true;
            comp.snippetKey = '';
            comp.internalFeedback = snippets[0].value;
            comp.findSnippet();
            expect(comp.snippetKey).toBe('');
        });

        it('should do nothing if the value in internalFeedback doesn\'t have a corresponding snippet', () => {
            comp.snippetKey = '';
            comp.internalFeedback = 'no snippet with this text';
            comp.findSnippet();
            expect(comp.snippetKey).toBe('');
        });

        it('should set the snippet key corresponding to the value in internalFeedback', () => {
            const { key, value } = snippets[0];
            comp.snippetKey = '';
            comp.internalFeedback = value;
            comp.findSnippet();
            expect(comp.snippetKey).toBe(key);
        });
    });
});
