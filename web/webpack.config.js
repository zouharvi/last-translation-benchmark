const path = require('path');
const HtmlWebpackPlugin = require('html-webpack-plugin');
const TerserPlugin = require('terser-webpack-plugin');
const MiniCssExtractPlugin = require('mini-css-extract-plugin');
const CopyWebpackPlugin = require('copy-webpack-plugin');

module.exports = (env, argv) => ({
  entry: {
    index: './src/index.ts',
    dashboard: './src/dashboard.ts',
    contributor: './src/contribute.ts',
    reviewer: './src/review.ts',
    profile: './src/profile.ts',
    admin: './src/admin.ts',
  },
  output: {
    filename: '[name].bundle.js',
    path: path.resolve(__dirname, '../server/static'),
    clean: {
      keep: /languages\.json/,
    },
  },
  optimization: {
    minimize: true,
    minimizer: [
      new TerserPlugin({
        extractComments: false,
        terserOptions: { format: { comments: false } },
      }),
    ],
  },
  module: {
    rules: [
      { test: /\.ts$/, use: 'ts-loader', exclude: /node_modules/ },
      { test: /\.css$/, use: [MiniCssExtractPlugin.loader, 'css-loader'] },
      { test: /src\/assets\/.*\.html$/, type: 'asset/source' }
    ],
  },
  resolve: { extensions: ['.ts', '.js'] },
  plugins: [
    new MiniCssExtractPlugin({ filename: 'style.css' }),
    new HtmlWebpackPlugin({
      template: './src/index.html',
      filename: 'index.html',
      chunks: ['index'],
      hash: true,
    }),
    new HtmlWebpackPlugin({
      template: './src/dashboard.html',
      filename: 'dashboard.html',
      chunks: ['dashboard'],
      hash: true,
    }),
    new HtmlWebpackPlugin({
      template: './src/contribute.html',
      filename: 'contribute.html',
      chunks: ['contributor'],
      hash: true,
    }),
    new HtmlWebpackPlugin({
      template: './src/review.html',
      filename: 'review.html',
      chunks: ['reviewer'],
      hash: true,
    }),
    new HtmlWebpackPlugin({
      template: './src/profile.html',
      filename: 'profile.html',
      chunks: ['profile'],
      hash: true,
    }),
    new HtmlWebpackPlugin({
      template: './src/admin.html',
      filename: 'admin.html',
      chunks: ['admin'],
      hash: true,
    }),

    new CopyWebpackPlugin({
      patterns: [
        { from: 'src/assets/', to: 'assets' },
        { from: 'src/robots.txt', to: 'robots.txt' }
      ],
    }),
  ],
  devServer: {
    static: '../server/static',
    port: 8000,
    open: true,
    proxy: [{ context: ['/api'], target: 'http://localhost:8000' }],
  },
  mode: argv.mode || 'development',
  devtool: argv.mode === 'production' ? false : 'source-map',
});
