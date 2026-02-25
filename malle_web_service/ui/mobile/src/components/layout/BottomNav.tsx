import { useLocation, useNavigate } from 'react-router-dom';

interface NavItem {
  id: string;
  label: string;
  icon: string;
  path: string;
  isCenter?: boolean;
}

const navItems: NavItem[] = [
  { id: 'home', label: 'Home', icon: 'home', path: '/' },
  { id: 'mode', label: 'Mode', icon: 'tune', path: '/mode' },
  { id: 'map', label: 'Map', icon: 'map', path: '/map', isCenter: true },
  { id: 'lockbox', label: 'Lockbox', icon: 'lock', path: '/lockbox' },
  { id: 'list', label: 'List', icon: 'receipt_long', path: '/list' },
];

export function BottomNav() {
  const location = useLocation();
  const navigate = useNavigate();

  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  };

  return (
    <nav className="fixed bottom-0 left-0 right-0 bg-card/90 dark:bg-card/90 backdrop-blur-xl border-t border-border pt-3 pb-8 px-4 z-30 shadow-[0_-5px_15px_rgba(0,0,0,0.02)]">
      <div className="flex justify-around items-end">
        {navItems.map((item) => (
          <button
            key={item.id}
            onClick={() => navigate(item.path)}
            className={`flex flex-col items-center transition-all active-press-sm ${
              item.isCenter ? 'relative -mt-6' : ''
            }`}
          >
            {item.isCenter ? (
              <div className={`w-14 h-14 rounded-full flex items-center justify-center shadow-lg transition-all ${
                isActive(item.path)
                  ? 'bg-foreground text-background'
                  : 'bg-foreground/90 text-background hover:bg-foreground'
              }`}>
                <span className="material-icons-round text-2xl">{item.icon}</span>
              </div>
            ) : (
              <div className={`flex flex-col items-center px-3 py-2 rounded-xl transition-all ${
                isActive(item.path)
                  ? 'bg-muted'
                  : 'hover:bg-muted/50'
              }`}>
                <span className={`material-icons-round text-xl transition-colors ${
                  isActive(item.path) ? 'text-foreground' : 'text-muted-foreground'
                }`}>
                  {item.icon}
                </span>
                <span className={`text-[10px] font-medium mt-1 transition-colors ${
                  isActive(item.path) ? 'text-foreground' : 'text-muted-foreground'
                }`}>
                  {item.label}
                </span>
              </div>
            )}
          </button>
        ))}
      </div>
    </nav>
  );
}
