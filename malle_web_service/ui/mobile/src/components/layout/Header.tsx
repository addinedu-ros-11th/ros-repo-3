import { useAppStore } from '@/store/appStore';

interface HeaderProps {
  onSearchClick: () => void;
  onProfileClick: () => void;
}

export function Header({ onSearchClick, onProfileClick }: HeaderProps) {
  return (
    <header className="pt-12 pb-4 px-6 flex justify-between items-center bg-card/80 dark:bg-card/80 backdrop-blur-lg shadow-sm z-20 sticky top-0">
      {/* Left: Notifications */}
      <button className="p-2 rounded-full hover:bg-muted transition-colors relative active-press-sm">
        <span className="material-icons-round text-muted-foreground text-3xl">notifications</span>
        <span className="absolute top-2 right-2 w-2.5 h-2.5 bg-destructive rounded-full border-2 border-card"></span>
      </button>

      {/* Right: Search + Profile */}
      <div className="flex items-center space-x-3">
        <button 
          onClick={onSearchClick}
          className="p-2 rounded-full hover:bg-muted transition-colors active-press-sm"
        >
          <span className="material-icons-round text-muted-foreground text-3xl">search</span>
        </button>
        <button 
          onClick={onProfileClick}
          className="w-10 h-10 rounded-full bg-gradient-to-tr from-card-purple to-card-pink p-0.5 active-press-sm"
        >
          <div className="w-full h-full rounded-full bg-gradient-to-br from-purple-400 to-pink-400 flex items-center justify-center text-white font-bold text-sm">
            S
          </div>
        </button>
      </div>
    </header>
  );
}
