<template>
    <div class="toggle-container">
        <div class="toggle" @click="onChange">
            <b-button class="off" variant="default">
                {{ labelOff }}
            </b-button>
            <b-button class="on" variant="primary">
                {{ labelOn }}
            </b-button>
        </div>
    </div>
</template>

<script>
export default {
    name: 'toggle',

    props: {
        value: {
            type: Boolean,
            default: false,
        },
        labelOn: {
            type: String,
            default: 'on',
        },
        labelOff: {
            type: String,
            default: 'off',
        },
    },

    data() {
        return {
            current: this.value,
        };
    },

    mounted() {
        this.update();
    },

    methods: {
        onChange() {
            this.current = !this.current;
            this.$emit('input', this.current);
            this.update();
        },

        update() {
            if (this.current) {
                this.$el.setAttribute('checked', 'checked');
            } else {
                this.$el.removeAttribute('checked');
            }
        },
    },
};
</script>

<style lang="less" scoped>
.toggle-container {
    display: inline-block;
    overflow: hidden;
    cursor: pointer;
    border-radius: .25rem;
}

.toggle {
    position: relative;
    width: 4rem;
    height: 2.25rem;

    .on,
    .off {
        position: absolute;
        top: 0;
        left: 0;
        display: block;
        width: 100%;
        height: 100%;
        transition: transform 300ms ease-out 0;
        padding: .375rem;
        pointer-events: none;
        text-align: center;
    }

    .off {
        transform: translateX(0);
    }

    .on {
        transform: translateX(100%);
    }

    [checked] & {
        .off {
            transform: translateX(-100%);
        }

        .on {
            transform: translateX(0);
        }
    }
}
</style>