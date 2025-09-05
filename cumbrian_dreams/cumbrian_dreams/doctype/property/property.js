frappe.ui.form.on("Property", {
	refresh(frm) {
		// Handy quick-action example
		frm.add_custom_button("Mark Inactive", () => {
			frm.set_value("disabled", 1);
			frm.save();
		}).addClass("btn-default");
	},
});
