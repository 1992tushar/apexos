/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // NOTE: `experimental.typedRoutes` was removed. ApexOS treats routes as data
  // (data-driven sidebar nav in nav-config.ts, breadcrumbs, and rowHref click
  // handlers), and several nav targets resolve through the `[module]` catch-all
  // rather than existing as static pages. typedRoutes cannot type those, so it
  // forced `as Route` casts everywhere and blocked the build. Re-enable only if
  // route strings become statically enumerable.
};

export default nextConfig;
