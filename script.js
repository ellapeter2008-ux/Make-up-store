
const CART_KEY = "beautyHavenCart";
const WISHLIST_KEY = "beautyHavenWishlist";
const ORDERS_KEY = "beautyHavenOrders";

const API_URL =  "http://127.0.0.1:5000/api";

async function loadProductsFromBackend() {
    try {
        const response = await fetch({API_URL}/products);

        if (!response.ok) {
            throw new Error("Failed to load products");
        }

        const data = await response.json();

        console.log("Products from backend:", data);

    } catch (error) {
        console.error("Backend connection error:", error);
    }
}

const FREE_DELIVERY_LIMIT = 70000;   // Free delivery at or above this subtotal
const STANDARD_DELIVERY_FEE = 0;     // Fee for orders under the limit (see note above)
const MAX_QUANTITY = 10;             // Matches max="10" in the HTML

let messageTimer = null;            

function getCartId() {
  let cartId = localStorage.getItem("beautyHavenCartId");

  if (!cartId) {
    cartId = crypto.randomUUID();
    localStorage.setItem("beautyHavenCartId", cartId);
  }

  return cartId;
}




// Turns 70000 into "₦70,000"
function formatNaira(amount) {
  return "₦" + Number(amount).toLocaleString("en-US");
}

// Turns "₦70,000" into the number 70000
function priceToNumber(text) {
  const digitsOnly = String(text).replace(/[^0-9.]/g, "");
  return Number(digitsOnly) || 0;
}

// Turns a product name into an id, e.g. "Beauty Blender" -> "beauty-blender"
// (the word "and" is removed so ids match the data-product-id values in the HTML)
function slugify(text) {
  return String(text)
    .toLowerCase()
    .replace(/\band\b/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

// Makes text safe to put inside HTML
function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// Changes the text of an element, only if the element exists
function setText(selector, text) {
  const element = document.querySelector(selector);
  if (element) {
    element.textContent = text;
  }
}

// Shows or hides an element, only if the element exists
function setHidden(element, shouldHide) {
  if (element) {
    element.hidden = shouldHide;
    element.style.display = shouldHide ? "none" : "";
  }
}

// Shows a message at the top of the page.
// type is "success" or "error". details is an optional list of extra lines.
function showMessage(text, type, details) {
  const oldBox = document.querySelector("#site-message");
  if (oldBox) {
    oldBox.remove();
  }
  clearTimeout(messageTimer);

  const box = document.createElement("div");
  box.id = "site-message";
  box.className = "site-message site-message-" + type;
  box.setAttribute("role", type === "error" ? "alert" : "status");

  const paragraph = document.createElement("p");
  paragraph.textContent = text;
  box.appendChild(paragraph);

  if (details && details.length > 0) {
    const list = document.createElement("ul");
    details.forEach(function (detail) {
      const item = document.createElement("li");
      item.textContent = detail;
      list.appendChild(item);
    });
    box.appendChild(list);
  }

  const main = document.querySelector("#main-content") || document.body;
  main.insertBefore(box, main.firstChild);
  box.scrollIntoView({ behavior: "smooth", block: "center" });

  // Success messages disappear by themselves. Error messages stay.
  if (type === "success") {
    messageTimer = setTimeout(function () {
      box.remove();
    }, 5000);
  }

  return box;
}

// Adds a link to the end of a message box
function appendLinkToMessage(box, linkText, linkUrl) {
  const link = document.createElement("a");
  link.href = linkUrl;
  link.textContent = linkText;
  box.appendChild(link);
}




// Reads a list (array) from localStorage. Returns [] if nothing is saved.
function readList(key) {
  try {
    const saved = localStorage.getItem(key);
    if (!saved) {
      return [];
    }
    const list = JSON.parse(saved);
    return Array.isArray(list) ? list : [];
  } catch (error) {
    return [];
  }
}

// Saves a list (array) to localStorage
function saveList(key, list) {
  try {
    localStorage.setItem(key, JSON.stringify(list));
  } catch (error) {
    console.log("Could not save to localStorage:", error);
  }
}



function getCart() {
  return readList(CART_KEY);
}

function saveCart(cart) {
  saveList(CART_KEY, cart);
  refreshCartDisplays();
}

// Every cart line is identified by product id + shade
function makeCartKey(id, shade) {
  return id + "|" + shade;
}

function findCartIndex(cart, key) {
  for (let i = 0; i < cart.length; i++) {
    if (makeCartKey(cart[i].id, cart[i].shade) === key) {
      return i;
    }
  }
  return -1;
}

// Adds a product to the cart (or increases its quantity if already there)
function addToCart(product) {
  const cart = getCart();
  const key = makeCartKey(product.id, product.shade);
  const index = findCartIndex(cart, key);

  if (index >= 0) {
    cart[index].quantity = Math.min(cart[index].quantity + product.quantity, MAX_QUANTITY);
  } else {
    cart.push(product);
  }
  saveCart(cart);
}

function setCartQuantity(key, newQuantity) {
  const cart = getCart();
  const index = findCartIndex(cart, key);
  if (index < 0) {
    return;
  }
  let quantity = Math.round(Number(newQuantity));
  if (isNaN(quantity) || quantity < 1) {
    quantity = 1;
  }
  if (quantity > MAX_QUANTITY) {
    quantity = MAX_QUANTITY;
  }
  cart[index].quantity = quantity;
  saveCart(cart);
}

function removeFromCart(key) {
  const cart = getCart();
  const index = findCartIndex(cart, key);
  if (index >= 0) {
    cart.splice(index, 1);
    saveCart(cart);
  }
}

function getCartItemCount() {
  const cart = getCart();
  let count = 0;
  cart.forEach(function (item) {
    count += Number(item.quantity) || 0;
  });
  return count;
}

function calculateSubtotal(cart) {
  let subtotal = 0;
  cart.forEach(function (item) {
    subtotal += (Number(item.price) || 0) * (Number(item.quantity) || 0);
  });
  return subtotal;
}

// Delivery fee for standard delivery
function getDeliveryFee(subtotal) {
  if (subtotal === 0) {
    return 0;
  }
  if (subtotal >= FREE_DELIVERY_LIMIT) {
    return 0;
  }
  return STANDARD_DELIVERY_FEE;
}

// Updates the number badge in the header (#cart-count)
function updateCartCount() {
  setText("#cart-count", getCartItemCount());
}

// Redraws everything that depends on the cart
function refreshCartDisplays() {
  updateCartCount();
  renderCartPage();
  renderCheckoutSummary();
}



// Product page: reads the main product (#product-title, #product-price, etc.)
function getProductFromProductPage() {
  const nameElement = document.querySelector("#product-title");
  const priceElement = document.querySelector("#product-price");
  if (!nameElement || !priceElement) {
    return null;
  }

  const brandElement = document.querySelector("#product-brand");
  const imageElement = document.querySelector("#product-main-image");
  const quantityInput = document.querySelector("#product-quantity");

  // Selected shade (radio buttons named "shade"). May be empty.
  let shade = "";
  const checkedShade = document.querySelector('input[name="shade"]:checked');
  if (checkedShade) {
    const shadeLabel = document.querySelector('label[for="' + checkedShade.id + '"]');
    shade = shadeLabel ? shadeLabel.textContent.trim() : checkedShade.value;
  }

  let quantity = quantityInput ? Math.round(Number(quantityInput.value)) : 1;
  if (isNaN(quantity) || quantity < 1) {
    quantity = 1;
  }
  if (quantity > MAX_QUANTITY) {
    quantity = MAX_QUANTITY;
  }

  const name = nameElement.textContent.trim();
  return {
    id: slugify(name),
    name: name,
    brand: brandElement ? brandElement.textContent.trim() : "",
    price: priceToNumber(priceElement.textContent),
    image: imageElement ? imageElement.getAttribute("src") : "",
    shade: shade,
    shadeLabel: "Shade",
    quantity: quantity
  };
}

// Product cards (home page, related products, recommended products)
function getProductFromCard(card, button) {
  const nameElement = card.querySelector(".product-name");
  const priceElement = card.querySelector(".product-price");
  if (!nameElement || !priceElement) {
    return null;
  }

  const brandElement = card.querySelector(".product-brand");
  const imageElement = card.querySelector(".product-image");
  const shadeValueElement = card.querySelector(".product-shade-value");
  const shadeBox = card.querySelector(".product-shade");

  const name = nameElement.textContent.trim();
  const idFromButton = button ? button.dataset.productId : "";

  // The shade text says "Available colour:" for some products
  let shadeLabel = "Shade";
  if (shadeBox && shadeBox.textContent.toLowerCase().indexOf("colour") !== -1) {
    shadeLabel = "Colour";
  }

  return {
    id: idFromButton || slugify(name),
    name: name,
    brand: brandElement ? brandElement.textContent.trim() : "",
    price: priceToNumber(priceElement.textContent),
    image: imageElement ? imageElement.getAttribute("src") : "",
    shade: shadeValueElement ? shadeValueElement.textContent.trim() : "",
    shadeLabel: shadeLabel,
    quantity: 1
  };
}


/* ==========================================================================
   PRODUCT PAGE
   Uses: #product-form, #product-quantity, input[name="shade"],
         #selected-shade-name, #add-to-cart-button
   ========================================================================== */
function setupProductPage() {
  const productForm = document.querySelector("#product-form");
  if (!productForm) {
    return;
  }

  // Show the chosen shade name when a shade is clicked
  const shadeInputs = document.querySelectorAll('input[name="shade"]');
  shadeInputs.forEach(function (input) {
    input.addEventListener("change", function () {
      const label = document.querySelector('label[for="' + input.id + '"]');
      setText("#selected-shade-name", label ? label.textContent.trim() : input.value);
    });
  });

  // "Add to Cart" (the form's submit button)
  productForm.addEventListener("submit", function (event) {
    event.preventDefault(); // Stay on this page instead of opening cart.html

    const product = getProductFromProductPage();
    if (!product) {
      return;
    }

    addToCart(product);
    const box = showMessage("Product added to cart!", "success");
    appendLinkToMessage(box, "View Cart", "cart.html");
  });
}

// "Add to Cart" buttons on product cards (not the main product button)
function handleCardAddToCart(button) {
  const card = button.closest(".product-card");
  if (!card) {
    return;
  }
  const product = getProductFromCard(card, button);
  if (!product) {
    return;
  }
  addToCart(product);
  const box = showMessage("Product added to cart!", "success");
  appendLinkToMessage(box, "View Cart", "cart.html");
}


/* ==========================================================================
   CART PAGE
   Uses: #cart-items-list, #empty-cart-message, #summary-subtotal,
         #summary-delivery-fee, #summary-total, #checkout-button,
         #free-delivery-status, #free-delivery-remaining,
         #free-delivery-remaining-amount, #free-delivery-progress
   ========================================================================== */
function setupCartPage() {
  const list = document.querySelector("#cart-items-list");
  if (!list) {
    return;
  }

  renderCartPage();

  // Clicks on + , - and Remove buttons
  list.addEventListener("click", function (event) {
    const button = event.target.closest("button[data-action]");
    const article = event.target.closest(".cart-item");
    if (!button || !article) {
      return;
    }

    const key = article.dataset.key;
    const action = button.dataset.action;
    const cart = getCart();
    const index = findCartIndex(cart, key);
    if (index < 0) {
      return;
    }

    if (action === "increase") {
      setCartQuantity(key, cart[index].quantity + 1);
    } else if (action === "decrease") {
      setCartQuantity(key, cart[index].quantity - 1); // never goes below 1
    } else if (action === "remove") {
      removeFromCart(key);
    }
  });

  // Typing a number in the quantity box
  list.addEventListener("change", function (event) {
    if (!event.target.classList.contains("quantity-input")) {
      return;
    }
    const article = event.target.closest(".cart-item");
    if (article) {
      setCartQuantity(article.dataset.key, event.target.value);
    }
  });

  // Don't go to checkout with an empty cart
  const checkoutButton = document.querySelector("#checkout-button");
  if (checkoutButton) {
    checkoutButton.addEventListener("click", function (event) {
      if (getCart().length === 0) {
        event.preventDefault();
        showMessage("Your cart is empty. Add a product before checking out.", "error");
      }
    });
  }
}

// Draws the cart items and the order summary
function renderCartPage() {
  const list = document.querySelector("#cart-items-list");
  if (!list) {
    return;
  }

  const cart = getCart();
  const emptyMessage = document.querySelector("#empty-cart-message");
  list.innerHTML = "";

  if (cart.length === 0) {
    if (emptyMessage) {
      emptyMessage.innerHTML = 'Your cart is empty. <a href="index.html">Continue Shopping</a>';
      setHidden(emptyMessage, false);
    }
  } else {
    setHidden(emptyMessage, true);
    cart.forEach(function (item, index) {
      list.insertAdjacentHTML("beforeend", buildCartItemHtml(item, index));
    });
  }

  updateCartSummary(cart);
}

// Builds the HTML for one cart item (same structure as cart.html)
function buildCartItemHtml(item, index) {
  const key = makeCartKey(item.id, item.shade);
  const lineTotal = item.price * item.quantity;
  const label = item.shadeLabel || "Shade";

  let shadeHtml = "";
  if (item.shade) {
    shadeHtml = `<p class="cart-item-shade">${escapeHtml(label)}: <span class="cart-item-shade-value">${escapeHtml(item.shade)}</span></p>`;
  }

  let brandHtml = "";
  if (item.brand) {
    brandHtml = `<p class="cart-item-brand">${escapeHtml(item.brand)}</p>`;
  }

  return `
    <li class="cart-item-wrapper">
      <article class="cart-item" data-key="${escapeHtml(key)}">
        <img class="cart-item-image" src="${escapeHtml(item.image || "")}" alt="${escapeHtml(item.name)}">
        <div class="cart-item-details">
          ${brandHtml}
          <h3 class="cart-item-name"><a class="cart-item-link" href="product.html">${escapeHtml(item.name)}</a></h3>
          ${shadeHtml}
          <p class="cart-item-price">Price: <span class="cart-item-price-value">${formatNaira(item.price)}</span></p>
        </div>
        <div class="cart-item-quantity quantity-selector">
          <button type="button" class="quantity-button quantity-decrease" data-action="decrease" aria-label="Decrease quantity of ${escapeHtml(item.name)}">−</button>
          <label for="quantity-${index}" class="quantity-label">Quantity</label>
          <input type="number" id="quantity-${index}" class="quantity-input" value="${item.quantity}" min="1" max="${MAX_QUANTITY}">
          <button type="button" class="quantity-button quantity-increase" data-action="increase" aria-label="Increase quantity of ${escapeHtml(item.name)}">+</button>
        </div>
        <p class="cart-item-total">Item total: <span class="cart-item-total-value">${formatNaira(lineTotal)}</span></p>
        <button type="button" class="button button-secondary remove-item-button" data-action="remove" aria-label="Remove ${escapeHtml(item.name)} from cart">Remove</button>
      </article>
    </li>`;
}

// Updates subtotal, delivery fee, total and the free delivery message
function updateCartSummary(cart) {
  const subtotal = calculateSubtotal(cart);
  const deliveryFee = getDeliveryFee(subtotal);
  const total = subtotal + deliveryFee;

  setText("#summary-subtotal", formatNaira(subtotal));
  setText("#summary-delivery-fee", formatNaira(deliveryFee));
  setText("#summary-total", formatNaira(total));

  updateFreeDeliveryMessage(subtotal);
}

// Free delivery message on the cart page
function updateFreeDeliveryMessage(subtotal) {
  const status = document.querySelector("#free-delivery-status");
  const remaining = document.querySelector("#free-delivery-remaining");
  const progress = document.querySelector("#free-delivery-progress");

  if (subtotal >= FREE_DELIVERY_LIMIT) {
    if (status) {
      status.textContent = "You've unlocked free delivery!";
      status.classList.add("free-delivery-unlocked");
    }
    setHidden(status, false);
    setHidden(remaining, true);
  } else {
    setHidden(status, true);
    setText("#free-delivery-remaining-amount", formatNaira(FREE_DELIVERY_LIMIT - subtotal));
    setHidden(remaining, false);
  }

  if (progress) {
    progress.max = FREE_DELIVERY_LIMIT;
    progress.value = Math.min(subtotal, FREE_DELIVERY_LIMIT);
  }
}


/* ==========================================================================
   SHADE MATCH FINDER
   Uses: #shade-finder-form, #skin-tone, #undertone, #existing-brand,
         #existing-shade, #shade-results
   ========================================================================== */

const SKIN_TONE_NAMES = {
  fair: "Fair",
  light: "Light",
  medium: "Medium",
  tan: "Tan",
  deep: "Deep",
  dark: "Dark"
};

const SKIN_TONE_TIPS = {
  fair: "Start with the lightest shades in a brand's range.",
  light: "Look at the light and light-medium shades.",
  medium: "Look at the shades in the middle of the brand's range.",
  tan: "Look at the tan, golden-medium and deeper-medium shades.",
  deep: "Look at the deep shades. Compare a few, as many brands offer several in this range.",
  dark: "Look at the deepest shades in the range and compare a few, as the differences can be subtle."
};

const UNDERTONE_INFO = {
  cool: { name: "Cool", look: "pink, rosy or bluish", words: "rose, pink or porcelain" },
  warm: { name: "Warm", look: "golden, yellow or peachy", words: "golden, honey or caramel" },
  neutral: { name: "Neutral", look: "a balance of warm and cool", words: "beige, natural or neutral" },
  olive: { name: "Olive", look: "a green-gold tint", words: "olive, golden or tan" }
};

function setupShadeFinder() {
  const form = document.querySelector("#shade-finder-form");
  const resultBox = document.querySelector("#shade-results");
  if (!form || !resultBox) {
    return;
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    showShadeResult(resultBox);
  });
}

function showShadeResult(resultBox) {
  const skinToneSelect = document.querySelector("#skin-tone");
  const undertoneSelect = document.querySelector("#undertone");
  const brandSelect = document.querySelector("#existing-brand");
  const shadeInput = document.querySelector("#existing-shade");

  const skinTone = skinToneSelect ? skinToneSelect.value : "";
  const undertone = undertoneSelect ? undertoneSelect.value : "";

  // Skin tone and undertone are required
  if (!SKIN_TONE_NAMES[skinTone] || !UNDERTONE_INFO[undertone]) {
    resultBox.innerHTML = '<p class="shade-result-error">Please choose both your skin tone and your undertone.</p>';
    return;
  }

  const skinName = SKIN_TONE_NAMES[skinTone];
  const undertoneData = UNDERTONE_INFO[undertone];
  const shadeName = skinName + " " + undertoneData.name;

  // Optional: existing brand and shade
  let brandText = "";
  if (brandSelect && brandSelect.value && brandSelect.value !== "none") {
    brandText = brandSelect.options[brandSelect.selectedIndex].text;
  }
  const existingShade = shadeInput ? shadeInput.value.trim() : "";

  let brandNote;
  if (brandText) {
    const shadePart = existingShade ? " in shade " + existingShade : "";
    brandNote = "You currently use " + brandText + shadePart + ". Try comparing it with " +
      skinName.toLowerCase() + " shades with a " + undertoneData.name.toLowerCase() +
      " undertone in other brands' ranges.";
  } else {
    brandNote = "Compare swatches across a few brands to find the shade that looks best on you.";
  }

  resultBox.innerHTML = `
    <article class="shade-result-card">
      <h3 class="shade-result-title">Your suggested shade: ${escapeHtml(shadeName)}</h3>
      <p class="shade-result-text">Look for a ${escapeHtml(skinName.toLowerCase())} shade with a ${escapeHtml(undertoneData.name.toLowerCase())} undertone (${escapeHtml(undertoneData.look)}). Shade names often include words like ${escapeHtml(undertoneData.words)}.</p>
      <p class="shade-result-text">${escapeHtml(SKIN_TONE_TIPS[skinTone])}</p>
      <p class="shade-result-text">${escapeHtml(brandNote)}</p>
      <p class="shade-result-note">This is a simple guide, not an exact match. Shades can look different in different lighting, so test or sample before you buy.</p>
      <a class="button button-primary" href="product.html">Browse Products</a>
    </article>`;
}


/* ==========================================================================
   WISHLIST
   Uses: #add-to-wishlist-button (product page) and
         .add-to-wishlist-button (product cards)
   ========================================================================== */

function getWishlist() {
  return readList(WISHLIST_KEY);
}

function isInWishlist(id) {
  const wishlist = getWishlist();
  for (let i = 0; i < wishlist.length; i++) {
    if (wishlist[i].id === id) {
      return true;
    }
  }
  return false;
}

// Adds the product if it is not in the wishlist, removes it if it is.
// Returns true if it was added, false if it was removed.
function toggleWishlist(product) {
  let wishlist = getWishlist();

  if (isInWishlist(product.id)) {
    wishlist = wishlist.filter(function (item) {
      return item.id !== product.id;
    });
    saveList(WISHLIST_KEY, wishlist);
    return false;
  }

  wishlist.push({
    id: product.id,
    name: product.name,
    brand: product.brand,
    price: product.price,
    image: product.image
  });
  saveList(WISHLIST_KEY, wishlist);
  return true;
}

function handleWishlistClick(button) {
  let product = null;

  if (button.id === "add-to-wishlist-button") {
    product = getProductFromProductPage();
  } else {
    const card = button.closest(".product-card");
    if (card) {
      product = getProductFromCard(card, button);
    }
  }
  if (!product) {
    return;
  }

  const wasAdded = toggleWishlist(product);
  updateWishlistButtons();
  showMessage(wasAdded ? "Added to your wishlist!" : "Removed from your wishlist.", "success");
}

// Changes every wishlist button's text depending on the saved wishlist
function updateWishlistButtons() {
  const buttons = document.querySelectorAll(".add-to-wishlist-button");

  buttons.forEach(function (button) {
    let id = "";
    if (button.id === "add-to-wishlist-button") {
      const title = document.querySelector("#product-title");
      id = title ? slugify(title.textContent.trim()) : "";
    } else {
      const card = button.closest(".product-card");
      const nameElement = card ? card.querySelector(".product-name") : null;
      id = button.dataset.productId || (nameElement ? slugify(nameElement.textContent.trim()) : "");
    }

    const saved = id !== "" && isInWishlist(id);
    button.textContent = saved ? "Remove from Wishlist" : "Add to Wishlist";
    button.setAttribute("aria-pressed", saved ? "true" : "false");
  });
}


/* ==========================================================================
   CLICK HANDLERS FOR PRODUCT CARDS (works on every page)
   ========================================================================== */
function setupCardButtons() {
  document.addEventListener("click", function (event) {
    // "Add to Cart" on a product card (the main product page button is
    // handled by the form's submit event instead)
    const cartButton = event.target.closest(".add-to-cart-button");
    if (cartButton && cartButton.id !== "add-to-cart-button") {
      handleCardAddToCart(cartButton);
      return;
    }

    // "Add to Wishlist" buttons
    const wishlistButton = event.target.closest(".add-to-wishlist-button");
    if (wishlistButton) {
      handleWishlistClick(wishlistButton);
    }
  });
}


/* ==========================================================================
   START EVERYTHING WHEN THE PAGE HAS LOADED
   ========================================================================== */
document.addEventListener("DOMContentLoaded", function () {
  updateCartCount();        // Header cart badge (all pages)
  setupCardButtons();       // Product card buttons (all pages)
  updateWishlistButtons();  // Wishlist button text (all pages)
  setupProductPage();       // Only runs on product.html
  setupCartPage();          // Only runs on cart.html
  setupShadeFinder();       // Only runs on index.html
  loadProductsFromBackend(); // Load products from backend
});