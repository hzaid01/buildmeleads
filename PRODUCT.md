# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

The public marketing and legal site is a separate static HTML/CSS/minimal-JavaScript surface deployed through GitHub Pages. It must not expose or bundle the private Node/FastAPI application.

## Users

BuildMeLeads is for local marketing agencies and independent marketers prospecting service businesses in the United States, United Kingdom, and Australia. They need a focused way to find businesses whose public Google Business Profile signals indicate an opportunity, prepare relevant outreach, and manage responsible delivery.

## Product Purpose

BuildMeLeads discovers plumbers, roofers, HVAC providers, electricians, and similar local businesses with missing websites or weak Google Business Profiles. The planned SaaS qualifies those leads, generates short personalized outreach with AI, and sends through a customer's configured provider with safeguards.

The current public release is a pre-launch marketing and waitlist site. It does not sell subscriptions, accept payments, create accounts, or provide application access.

## Positioning

BuildMeLeads connects opportunity discovery and concise personalized outreach in one workflow, using observable public business-profile weaknesses as the reason for each message rather than producing generic lead lists or generic sales copy.

## Operating Context

Visitors primarily arrive from X on mobile. The public site must explain the product quickly, show planned monthly pricing, collect waitlist interest through Google Forms, and provide clear legal and contact information for Paddle domain review.

## Capabilities and Constraints

- Brand and domain: BuildMeLeads / Lead Scout (configurable domain).
- Planned tiers: Starter at $49/month, Pro at $99/month, and Agency at $299/month.
- Pricing is informational during pre-launch; there is no checkout or payment collection.
- The primary action is `Reserve Your Spot` and opens or focuses the waitlist form.
- Confirmed waitlist thank-you promise: launch updates and an exclusive founding-member discount; do not expand that into a guaranteed price or discount amount.
- The public site has no login, signup, dashboard, application API, or local database dependency.
- The SaaS uses public-source business data, Groq, Apify, SendGrid and/or the Gmail API.
- Outreach customers remain responsible for lawful use and applicable anti-spam compliance.

## Brand Commitments

- Public name: BuildMeLeads.
- Project Type: Open-source B2B Lead Discovery & Outreach Engine.
- Public support and privacy email: `support@example.com`.
- Voice: clear, specific, confident, responsible, and human; avoid hype, invented proof, and generic sales language.

## Evidence on Hand

The repository contains a working private lead-discovery and outreach application with local/cloud discovery, Groq copy generation, Gmail OAuth, SendGrid support, tenant isolation, suppression handling, send caps, and validation safeguards. There are no approved testimonials, customer logos, usage statistics, performance benchmarks, or public product screenshots; the marketing site must not invent them.

## Product Principles

1. Show the mechanism, not inflated claims.
2. Make pre-launch status and planned pricing unmistakable.
3. Present responsible outreach as a product requirement, not fine print.
4. Keep the public surface lightweight, fast, mobile-first, and separate from the application.
5. Make seller identity, policies, and contact routes easy to find.

## Accessibility & Inclusion

The public site targets WCAG 2.2 AA, supports keyboard navigation and reduced motion, uses semantic HTML, and remains usable from 320px mobile widths through large desktop screens.
