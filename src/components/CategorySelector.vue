<!-- SPDX-License-Identifier: AGPL-3.0-only -->
<template>
<div class="categories">
    <div class="category"
         :class="{selected: cat.name === value}"
         v-for="cat in categories"
         v-if="cat.enabled"
         @click="processInput(cat.name, false)"
         :key="cat.name">
        <span>{{ cat.name }}</span>
        <div class="indicator"/>
    </div>
</div>
</template>

<script>
export default {
    name: 'category-selector',

    props: {
        value: {
            type: String,
            required: true,
        },

        categories: {
            type: Array,
            required: true,
        },

        default: {
            type: String,
            required: true,
        },
    },

    computed: {
        enabledCats() {
            return this.categories.filter(cat => cat.enabled);
        },
    },

    watch: {
        enabledCats: {
            immediate: true,
            handler() {
                this.$emit('input', this.getInitialValue());
            },
        },

        $route(newVal) {
            let val = decodeURI(newVal.hash && newVal.hash.slice(1)) || this.default;
            if (val !== this.value) {
                // Selected value is not available
                if (!this.enabledCats.find(x => x.name === val)) {
                    // Keep the same value
                    if (
                        this.enabledCats.find(x => x.name === this.value) ||
                        this.enabledCats.length === 0
                    ) {
                        val = this.value;
                    } else {
                        val = this.enabledCats[0];
                    }
                }
                this.processInput(val, true);
            }
        },
    },

    methods: {
        getInitialValue() {
            const hash = decodeURI(this.$route.hash && this.$route.hash.slice(1));
            if (hash) {
                return hash;
            }
            if (this.enabledCats.length === 0) {
                return this.default;
            }
            const hasDefault = this.enabledCats.filter(cat => cat.name === this.default).length > 0;
            if (hasDefault) {
                return this.default;
            }
            return this.enabledCats[0].name;
        },

        processInput(catName, forceEmit) {
            if (forceEmit || catName !== this.value) {
                this.$router.replace(
                    Object.assign({}, this.$route, {
                        hash: `#${catName || this.default}`,
                    }),
                );
                this.$emit('input', catName);
            }
        },
    },
};
</script>

<style lang="less">
@import '~mixins.less';

.categories {
    display: flex;
    flex-direction: row;
}

.category {
    flex: 1 1 auto;
    display: flex;
    flex-direction: column;
    line-height: 1rem;
    padding: 0 1rem;
    cursor: pointer;

    .categories:last-child & {
        margin-bottom: -1rem;

        @media @media-small {
            margin-bottom: -0.8rem;
        }
    }

    .indicator {
        border-bottom: 2px solid transparent;
        width: 75%;
        margin: 0 auto;
    }

    &.selected .indicator {
        border-bottom: 2px solid @color-primary;
        #app.dark & {
            border-bottom: 2px solid @color-secondary;
        }
    }

    &:hover .indicator {
        border-bottom: 2px solid lighten(@color-secondary, 20%);
    }

    span {
        text-align: center;
        padding-bottom: 0.25rem;
        padding: 0.5rem;
        font-size: 0.75rem;
    }
}
</style>
