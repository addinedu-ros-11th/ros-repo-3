from base import ok, get, post, patch, delete, health

USER_ID = 1


def test_list_pois():
    print("\n[pois] POI 목록")
    data = ok("GET /pois", get("/pois"))
    pois = data if isinstance(data, list) else data.get("pois", [])
    print(f"       → {len(pois)}개")
    for p in pois[:5]:
        print(f"         id={p['id']} name={p['name']} type={p['type']}")
    if len(pois) > 5:
        print(f"         ... 외 {len(pois)-5}개")
    return pois


def test_list_stores():
    print("\n[stores] 스토어 목록")
    data = ok("GET /stores", get("/stores"))
    stores = data if isinstance(data, list) else data.get("stores", [])
    print(f"         → {len(stores)}개")
    for s in stores:
        print(f"           id={s['id']} poi_id={s.get('poi_id')} category={s.get('category')}")
    return stores


def test_store_products(store_id: int):
    print(f"\n[stores] 상품 목록 (store={store_id})")
    data = ok(f"GET /stores/{store_id}/products", get(f"/stores/{store_id}/products"))
    products = data if isinstance(data, list) else data.get("products", [])
    print(f"         → {len(products)}개")
    for p in products:
        print(f"           id={p['id']} name={p['name']} price={p.get('price')}")
    return products


def test_shopping_lists():
    print(f"\n[shopping] 쇼핑 리스트 (user={USER_ID})")
    data = ok(f"GET /users/{USER_ID}/shopping-lists", get(f"/users/{USER_ID}/shopping-lists"))
    lists = data if isinstance(data, list) else data.get("shopping_lists", [])
    print(f"           → 기존 리스트 수: {len(lists)}")
    return lists


def test_create_shopping_list() -> dict:
    print(f"\n[shopping] 쇼핑 리스트 생성 (user={USER_ID})")
    data = ok("POST shopping-lists", post(f"/users/{USER_ID}/shopping-lists", {
        "name": "테스트 쇼핑 리스트"
    }))
    if data.get("id"):
        print(f"           → list_id={data['id']} name={data.get('name')}")
    return data


def test_add_item(list_id: int, store_id: int, product_id: int) -> dict:
    print(f"\n[shopping] 아이템 추가 (list={list_id})")
    data = ok("POST items", post(f"/shopping-lists/{list_id}/items", {
        "store_id": store_id,
        "product_id": product_id,
        "qty": 1,
        "unit_price": 45.90,
    }))
    if data.get("id"):
        print(f"           → item_id={data['id']}")
    return data


def test_update_item(list_id: int, item_id: int):
    print(f"\n[shopping] 아이템 수량 변경 (list={list_id} item={item_id})")
    ok("PATCH item qty=3", patch(f"/shopping-lists/{list_id}/items/{item_id}", {
        "qty": 3
    }))


def test_delete_item(list_id: int, item_id: int):
    print(f"\n[shopping] 아이템 삭제 (list={list_id} item={item_id})")
    ok("DELETE item", delete(f"/shopping-lists/{list_id}/items/{item_id}"))


if __name__ == "__main__":
    health()

    test_list_pois()

    stores = test_list_stores()
    if stores:
        test_store_products(stores[0]["id"])

    test_shopping_lists()
    sl = test_create_shopping_list()

    if sl.get("id") and stores:
        products = test_store_products(stores[0]["id"])
        if products:
            item = test_add_item(sl["id"], stores[0]["id"], products[0]["id"])
            if item.get("id"):
                test_update_item(sl["id"], item["id"])
                test_delete_item(sl["id"], item["id"])

    print("\n완료.")
