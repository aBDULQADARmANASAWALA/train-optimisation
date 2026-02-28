# 📁 `src/App.tsx`

## Overview
The main entry component for the RailOrchestra dashboard. It handles the primary layout structure, provides global data context, and manages top-level navigation state.

---

## Functions & Logic

### `App()` (Default Export)
```tsx
export default function App()
```
- **Description**: The root React component.
- **State Management**:
  - `activeTab`: Tracks the current view (`dashboard`, `trains`, `network`, `schedule`, `logs`).
  - `systemStatus`: Tracks whether the railway system is `'running'` or `'frozen'`.
- **Layout Structure**:
  - Wrapped in `<LiveDataProvider>` for real-time data access.
  - Responsive flex container with a fixed `Sidebar`.
  - Main area containing the `Header` and the dynamically rendered view.

### `renderContent()`
```tsx
const renderContent = () => { ... }
```
- **Description**: A helper function (defined within `App`) that returns the React component matching the `activeTab` state.
- **Views**:
  - `dashboard` -> `<Dashboard />`
  - `trains` -> `<TrainList />`
  - `network` -> `<NetworkMap />`
  - `schedule` -> `<ScheduleView />`
  - `logs` -> `<LogsView />`

---

## Suggested Code Improvement (Internal)
I've reviewed `App.tsx` and it looks correct. The only tiny concern is the `lastRunTimestamp={new Date().toISOString()}` in line 47. This will change on **every** re-render of `App` (e.g. when you click a sidebar tab), which might cause unnecessary re-renders in the `Header`. If that becomes a performance issue, it should be moved into a state or memo hook.
