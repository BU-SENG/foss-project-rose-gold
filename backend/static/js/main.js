// Mobile navigation toggle
document.addEventListener('DOMContentLoaded', function() {
	const btn = document.querySelector('.nav-toggle');
	const nav = document.querySelector('.nav');
	if (!btn || !nav) return;

	btn.addEventListener('click', function() {
		const isOpen = nav.classList.toggle('open');
		btn.setAttribute('aria-expanded', String(isOpen));
	});

	// Close nav when clicking outside on small screens
	document.addEventListener('click', function(e){
		if (!nav.classList.contains('open')) return;
		const target = e.target;
		if (target === nav || nav.contains(target) || target === btn) return;
		nav.classList.remove('open');
		btn.setAttribute('aria-expanded','false');
	});

	// Alerts: wire close buttons and auto-dismiss success/info
	const alerts = document.querySelectorAll('.alert');
	alerts.forEach(alert => {
		const close = alert.querySelector('.alert-close');
		if (close) {
			close.addEventListener('click', function(){
				alert.classList.add('closing');
				setTimeout(()=>alert.remove(), 300);
			});
		}

		// Auto-dismiss success/info alerts after 5s
		if (alert.classList.contains('alert-success') || alert.classList.contains('alert-info')){
			setTimeout(()=>{
				if (!document.body.contains(alert)) return;
				alert.classList.add('closing');
				setTimeout(()=>alert.remove(), 300);
			}, 5000);
		}
	});
});

// Page transition: intercept internal link clicks and play exit animation
document.addEventListener('DOMContentLoaded', function() {
	const main = document.querySelector('.main-content');
	if (!main) return;

	document.addEventListener('click', function(e){
		const a = e.target.closest('a');
		if (!a) return;
		// skip external links, anchors, mailto/tel, or links with target/_blank
		const href = a.getAttribute('href');
		if (!href || href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('tel:')) return;
		if (a.target && a.target !== '' && a.target !== '_self') return;
		// same origin check
		try {
			const url = new URL(href, window.location.href);
			if (url.origin !== window.location.origin) return;
		} catch (err){
			return; // malformed URL
		}

		// allow opt-out using data-no-transition
		if (a.hasAttribute('data-no-transition')) return;

		// only intercept left-clicks without modifier keys
		if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;

		e.preventDefault();
		main.classList.add('page-exit');

		// after the animation ends, navigate
		const onAnimEnd = function(){
			window.location.href = a.href;
		};

		// fallback in case animationend doesn't fire
		setTimeout(onAnimEnd, 350);
	});
});
