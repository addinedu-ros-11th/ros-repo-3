import React from 'react';

interface MaterialIconProps {
  icon: string;
  className?: string;
}

export const MI: React.FC<MaterialIconProps> = ({ icon, className = '' }) => (
  <span className={`material-icons-round ${className}`}>{icon}</span>
);
