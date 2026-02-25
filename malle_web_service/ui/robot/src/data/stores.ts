import type { Store, Product } from '@/types/robot';

export const stores: Store[] = [
  { id: 'zara', name: 'Zara', category: 'Fashion & Apparel', location: 'Level 2, Zone B', icon: 'checkroom', open: true },
  { id: 'nike', name: 'Nike', category: 'Sports & Outdoor', location: 'Level 1, Zone A', icon: 'sports_basketball', open: true },
  { id: 'apple', name: 'Apple', category: 'Electronics', location: 'Level 2, Zone C', icon: 'laptop_mac', open: true },
  { id: 'intersport', name: 'Intersport', category: 'Sports & Outdoor', location: 'Level 2, Zone B', icon: 'sports_basketball', open: true },
  { id: 'starbucks', name: 'Starbucks', category: 'Dining', location: 'Level 1, Zone B', icon: 'local_cafe', open: true },
  { id: 'progym', name: 'ProGym Equipment', category: 'Fitness', location: 'Ground Floor', icon: 'fitness_center', open: false },
  { id: 'uniqlo', name: 'Uniqlo', category: 'Fashion & Apparel', location: 'Level 1, Zone C', icon: 'checkroom', open: true },
  { id: 'sephora', name: 'Sephora', category: 'Beauty', location: 'Level 2, Zone A', icon: 'spa', open: true },
  { id: 'mcdonalds', name: "McDonald's", category: 'Dining', location: 'Ground Floor', icon: 'restaurant', open: true },
  { id: 'samsung', name: 'Samsung', category: 'Electronics', location: 'Level 2, Zone C', icon: 'phone_android', open: true },
];

export const products: Product[] = [
  // Zara
  { id: 'z1', name: 'Cotton T-Shirt', price: 29.99, storeId: 'zara' },
  { id: 'z2', name: 'Slim Fit Jeans', price: 59.99, storeId: 'zara' },
  { id: 'z3', name: 'Wool Coat', price: 149.99, storeId: 'zara' },
  // Nike
  { id: 'n1', name: 'Air Max Sneakers', price: 179.99, storeId: 'nike' },
  { id: 'n2', name: 'Running Shorts', price: 45.00, storeId: 'nike' },
  { id: 'n3', name: 'Dri-FIT T-Shirt', price: 35.00, storeId: 'nike' },
  // Apple
  { id: 'a1', name: 'iPhone Case', price: 49.00, storeId: 'apple' },
  { id: 'a2', name: 'AirPods Pro', price: 249.00, storeId: 'apple' },
  { id: 'a3', name: 'MagSafe Charger', price: 39.00, storeId: 'apple' },
  // Starbucks
  { id: 's1', name: 'Caffe Latte', price: 5.75, storeId: 'starbucks' },
  { id: 's2', name: 'Caramel Macchiato', price: 6.25, storeId: 'starbucks' },
  { id: 's3', name: 'Cold Brew', price: 4.95, storeId: 'starbucks' },
  // Intersport
  { id: 'i1', name: 'Yoga Mat', price: 34.99, storeId: 'intersport' },
  { id: 'i2', name: 'Hiking Boots', price: 129.99, storeId: 'intersport' },
  { id: 'i3', name: 'Tennis Racket', price: 89.99, storeId: 'intersport' },
  { id: 'i4', name: 'Swimming Goggles', price: 24.99, storeId: 'intersport' },
  { id: 'i5', name: 'Basketball', price: 39.99, storeId: 'intersport' },
  // Uniqlo
  { id: 'u1', name: 'Heattech Thermal', price: 19.99, storeId: 'uniqlo' },
  { id: 'u2', name: 'Ultra Light Down', price: 79.99, storeId: 'uniqlo' },
  { id: 'u3', name: 'Flannel Shirt', price: 39.99, storeId: 'uniqlo' },
  { id: 'u4', name: 'Chino Pants', price: 49.99, storeId: 'uniqlo' },
  { id: 'u5', name: 'Airism T-Shirt', price: 14.99, storeId: 'uniqlo' },
  // Sephora
  { id: 'se1', name: 'Lip Gloss Set', price: 28.00, storeId: 'sephora' },
  { id: 'se2', name: 'Foundation SPF30', price: 42.00, storeId: 'sephora' },
  { id: 'se3', name: 'Perfume Mini Set', price: 65.00, storeId: 'sephora' },
  { id: 'se4', name: 'Eye Shadow Palette', price: 54.00, storeId: 'sephora' },
  { id: 'se5', name: 'Skincare Kit', price: 89.00, storeId: 'sephora' },
  // McDonald's
  { id: 'mc1', name: 'Big Mac Meal', price: 9.99, storeId: 'mcdonalds' },
  { id: 'mc2', name: 'McNuggets 10pc', price: 7.49, storeId: 'mcdonalds' },
  { id: 'mc3', name: 'McFlurry Oreo', price: 4.29, storeId: 'mcdonalds' },
  { id: 'mc4', name: 'Quarter Pounder', price: 8.99, storeId: 'mcdonalds' },
  { id: 'mc5', name: 'Filet-O-Fish', price: 6.99, storeId: 'mcdonalds' },
  // Samsung
  { id: 'sm1', name: 'Galaxy Buds', price: 149.99, storeId: 'samsung' },
  { id: 'sm2', name: 'Phone Case', price: 29.99, storeId: 'samsung' },
  { id: 'sm3', name: 'Wireless Charger', price: 59.99, storeId: 'samsung' },
  { id: 'sm4', name: 'Galaxy Watch Band', price: 44.99, storeId: 'samsung' },
  { id: 'sm5', name: 'USB-C Cable', price: 19.99, storeId: 'samsung' },
];

export const storeCategories = ['All', 'Stores', 'Products', 'Services', 'Dining'];

export function getStoreById(id: string): Store | undefined {
  return stores.find(store => store.id === id);
}

export function getProductsByStore(storeId: string): Product[] {
  return products.filter(product => product.storeId === storeId);
}

export function searchStores(query: string, category: string = 'All'): Store[] {
  const lowerQuery = query.toLowerCase();
  return stores.filter(store => {
    const matchesQuery = store.name.toLowerCase().includes(lowerQuery) ||
      store.category.toLowerCase().includes(lowerQuery) ||
      store.location.toLowerCase().includes(lowerQuery);
    
    if (category === 'All') return matchesQuery;
    if (category === 'Stores') return matchesQuery;
    if (category === 'Dining') return matchesQuery && store.category === 'Dining';
    return matchesQuery;
  });
}
