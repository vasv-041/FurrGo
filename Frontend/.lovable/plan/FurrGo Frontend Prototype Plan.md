# FurrGo Frontend Prototype Plan

## Goal
Build a polished, mobile-first FurrGo prototype that immediately communicates: improving your own health strengthens your bond with the panda. The supplied images will guide mood, character prominence, and feature coverage only; the app will use an original FurrGo visual identity and original generated artwork.

## Experience structure
- Start at `/` with the onboarding choice between **Gamified** and **Clean**, with Gamified preselected.
- After continuing, open the shared app shell with working navigation for Home, Pet, Fitness, Rewards, and Profile.
- Add working secondary views for Medication, FurrGo AI, Medical Translator, Health Digest, and Goals.
- Preserve the selected mode, health activity, panda state, rewards, and equipped items locally between refreshes.
- Keep all information simulated; no login, backend, external health connection, AI service, report processing, or medical diagnosis.

## Shared prototype state
Create one client-side FurrGo state model used by both presentations:
- Vasu’s steps, sleep, medication, workouts, streak, weekly totals, goals, and recent activity.
- Bond level and XP, unlocks, collectibles, achievements, equipped outfit/room/accessory/emote.
- Panda mood derived from health actions: happy, energetic, sleepy, proud, excited, surprised, thinking, encouraging, and celebrating.
- Mode choice and onboarding completion.
- Local persistence with safe hydration so both modes always show the same underlying values.

## Gamified mode
- Build a mint, forest-green, and cream mobile experience with organic room scenes, rounded 16–24px surfaces, soft shadows, pastel health accents, and friendly typography.
- Create an original panda mascot and a cohesive cozy-room asset set rather than embedding or copying the reference sheets.
- Make the panda the emotional focal point: idle breathing/blinking, tap reactions, waves, sleepy posture, workout bounce, medication smile, milestone surprise, and level-up celebration.
- Add restrained particles, hearts, floating XP, progress count-up, confetti, page transitions, press feedback, and reward modal motion with reduced-motion support.

## Screens and interactions
1. **Onboarding** — panda-led welcome, two large mode choices, clear feature comparison, and Continue.
2. **Home** — greeting, streak, living room scene, speech bubble, Bond Level 3 and 340/500 XP, steps/sleep/medication cards, quick links, and clickable health-to-bond timeline.
3. **Pet** — large room and panda with Overview, Bonding, Rewards, Closet, and History tabs. Completed bonding actions animate the panda, add XP once, update mood/progress, and show feedback.
4. **Fitness** — circular 6,842/10,000 progress, active minutes, calories, workouts, weekly progress, goals, and simulated progress actions with milestone reactions.
5. **Medication** — morning/afternoon/evening schedule with usable completion controls, on-time feedback, persistent status, XP effects, and happy panda reaction.
6. **Rewards** — level progress, stats, Unlockables, Collectibles, and Achievements with locked/unlocked states and an Equip unlock modal.
7. **Closet** — panda preview with Outfit, Accessory, Room, and Emote categories; unlocked items equip immediately and locked items explain requirements.
8. **FurrGo AI** — friendly mock chat using AI Elements for the transcript, messages, loading state, and composer; suggested prompts return predefined educational responses and no medical diagnosis.
9. **Medical Translator** — interactive mock upload/drop state, sample document processing state, and plain-language term explanations.
10. **Health Digest** — weekly metrics, simple charts, streak summary, and Panda’s Weekly Note.
11. **Profile / Goals** — profile summary, health goals, preferences, notifications, privacy, settings, and mode switching with confirmation.

## Clean mode
- Present the exact same state through a calm, minimal, data-first interface with more whitespace, restrained motion, smaller panda moments, clear metrics, recent activity, weekly charts, AI entry point, and health summary.
- Keep the same navigation destinations and controls while removing XP-heavy emphasis and decorative game feedback.
- Show a confirmation before switching modes and explicitly reassure the user that health data and progress remain unchanged.

## Components and visual system
- Define semantic color, surface, shadow, radius, typography, and mode tokens in the global design system; use the supplied palette as the foundation without excessive gradients.
- Build reusable app shell, bottom navigation, panda stage, room scene, metric cards, progress displays, charts, activity rows, reward tiles, tabs, toast, and modal components.
- Use existing shadcn-compatible controls and Lucide icons for interface actions; install only the required UI primitives.
- Use original panda artwork as the identity, not a generic AI icon.
- Ensure stable layouts and readable controls from iPhone widths through Android phones and tablets; Gamified stays phone-like on larger screens rather than turning into a desktop dashboard.

## Technical implementation
- Keep TanStack Start routing and add route files for every navigable destination.
- Add Framer Motion for character and interface animation.
- Before implementing chat, check the current AI Elements registry documentation and install the Conversation, Message, Prompt Input, and Shimmer source components.
- Use Recharts or lightweight CSS/SVG displays for mock trends where appropriate.
- Add route-specific title, description, Open Graph, and Twitter metadata for every content route.
- Keep all data and responses in typed frontend fixtures/context; no server functions or network writes.

## Validation
- Run the project’s lint, full typecheck/build, and focused interaction checks.
- Verify onboarding, all navigation, tabs, mock chat, upload state, medication completion, XP updates, panda reactions, reward unlock/equip, closet changes, mode switching, and refresh persistence.
- Check representative iPhone, Android, and tablet sizes for clipping, overlap, fixed bottom-navigation spacing, and readable text.
- Confirm Clean and Gamified modes display identical health values after changes, assistant messages remain unfilled/readable, and reduced-motion behavior is respected.
