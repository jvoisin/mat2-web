const path = require('path');
const cssnano = require('cssnano')
const purgecss = require('@fullhuman/postcss-purgecss')

module.exports = (ctx) => ({
    plugins: [
        require('@tailwindcss/postcss'),
        require('autoprefixer'),
        process.env.NODE_ENV === 'production' ? cssnano({ preset: 'default' }) : null,
        ctx.env === 'production' && purgecss({
            content: [
                path.resolve(__dirname, 'templates/**/*.html')
            ],
            defaultExtractor: content => content.match(/[A-Za-z0-9-_:/]+/g) || []
        })
    ]
})