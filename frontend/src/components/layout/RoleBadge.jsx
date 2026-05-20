/**
 * RoleBadge — displays user's RBAC role with color coding.
 * 
 * Colors from AGNNTS.md:
 *   engineering = violet, finance = emerald, marketing = orange
 *   hr = rose, c_suite = amber, employee = slate
 */

const ROLE_CONFIG = {
  engineering: {
    label: 'Engineering Team',
    bg: 'bg-violet-500/20',
    text: 'text-violet-300',
    border: 'border-violet-500/30',
    dot: 'bg-violet-500',
  },
  finance: {
    label: 'Finance Team',
    bg: 'bg-emerald-500/20',
    text: 'text-emerald-300',
    border: 'border-emerald-500/30',
    dot: 'bg-emerald-500',
  },
  marketing: {
    label: 'Marketing Team',
    bg: 'bg-orange-500/20',
    text: 'text-orange-300',
    border: 'border-orange-500/30',
    dot: 'bg-orange-500',
  },
  hr: {
    label: 'HR Team',
    bg: 'bg-rose-500/20',
    text: 'text-rose-300',
    border: 'border-rose-500/30',
    dot: 'bg-rose-500',
  },
  c_suite: {
    label: 'C-Suite Executive',
    bg: 'bg-amber-500/20',
    text: 'text-amber-300',
    border: 'border-amber-500/30',
    dot: 'bg-amber-500',
  },
  employee: {
    label: 'Employee',
    bg: 'bg-slate-500/20',
    text: 'text-slate-300',
    border: 'border-slate-500/30',
    dot: 'bg-slate-500',
  },
}

export default function RoleBadge({ role }) {
  const config = ROLE_CONFIG[role] || ROLE_CONFIG.employee

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full border ${config.bg} ${config.border}`}>
      {/* Lock icon */}
      <svg
        className="w-3.5 h-3.5 text-slate-400"
        fill="none"
        viewBox="0 0 24 24"
        strokeWidth={2}
        stroke="currentColor"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 0 0 2.25-2.25v-6.75a2.25 2.25 0 0 0-2.25-2.25H6.75a2.25 2.25 0 0 0-2.25 2.25v6.75a2.25 2.25 0 0 0 2.25 2.25Z"
        />
      </svg>

      {/* Role dot indicator */}
      <div className={`w-2 h-2 rounded-full ${config.dot}`} />

      {/* Role label */}
      <span className={`text-xs font-medium ${config.text}`}>
        {config.label}
      </span>
    </div>
  )
}
