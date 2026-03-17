import { NavLink, useLocation } from 'react-router-dom';
import { useRobotStore } from '@/stores/robotStore';

interface NavItem {
  path: string;
  icon: string;
  label: string;
  requiresSession?: boolean;
}

const navItems: NavItem[] = [
  { path: '/', icon: 'home', label: 'Home' },
  { path: '/mode', icon: 'tune', label: 'Mode', requiresSession: true },
  { path: '/map', icon: 'map', label: 'Map', requiresSession: true },
  { path: '/lockbox', icon: 'lock', label: 'Lockbox', requiresSession: true },
  { path: '/search', icon: 'search', label: 'Search', requiresSession: true },
];

export function LeftSidebar() {
  const location = useLocation();
  const sessionState = useRobotStore((state) => state.sessionState);
  const isSessionActive = sessionState === 'ACTIVE';

  return (
    <aside className="w-20 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 fixed left-0 top-14 bottom-0 z-20 flex flex-col items-center py-6 space-y-2">
      {navItems.map((item) => {
        const isActive = item.path === '/' 
          ? location.pathname === '/' 
          : location.pathname.startsWith(item.path);
        const isDisabled = item.requiresSession && !isSessionActive;

        if (isDisabled) {
          return (
            <div
              key={item.path}
              className="nav-item-disabled"
              title="Session required"
            >
              <span className="material-icons-round text-xl">{item.icon}</span>
              <span className="text-[10px] font-medium mt-1">{item.label}</span>
            </div>
          );
        }

        return (
          <NavLink
            key={item.path}
            to={item.path}
            className={isActive ? 'nav-item-active' : 'nav-item-inactive'}
          >
            <span className="material-icons-round text-xl">{item.icon}</span>
            <span className="text-[10px] font-medium mt-1">{item.label}</span>
          </NavLink>
        );
      })}
    </aside>
  );
}
