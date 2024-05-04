var startingData;
// carica i dati iniziali all'interno della pagina
function init() {
	if (startingData != null) {
		$('#container').html(startingData);
	}
}

// permette di inviare richieste AJAX al server in base ad alcuni parametri
function request(method, url, parameters, callback) {
	$.ajax({
		type: method,
		url: localStorage.getItem('addr')+'/'+url,
		data: JSON.stringify(parameters),
		contentType: 'application/json',
		dataType: 'json',
		headers: { 'token': getCookie('token'), 'sub': getCookie('sub')},
		success: function (resultData) {
			try {
				resultData = JSON.parse(resultData);
			} catch (e) {
			}
			callback(resultData);
		},
		error: function (resultData) {
			try {
				resultData = resultData['responseJSON'];
				console.log('Errore: '+resultData['message'])
			} catch (e) {
				// se la risposra d'errore non contiene JSON, non è stato il server a rispondere
				resultData = {'invalidToken': true, 'message': 'Errore generale'}
			}
			// valuta se considerare il token come invalido
			if (resultData == undefined || 'invalidToken' in resultData && resultData['invalidToken']) {
				console.log('Errore grave nella richiesta')
				setCookie('token', '', 0);
				parent.showLogin();
			}
			showErrorAlert(resultData);
		}
	});
}

// mostra il form di login
function showLogin() {
	if (getCookie('token') == '') {
		$("#loginModal").modal({
			backdrop: 'static',
			keyboard: false
		});
	} else {
		fetchSections();
	}
}

// permette di impostare un cookie
function setCookie(cname, cvalue, exmin) {
	var d = new Date();
	d.setTime(d.getTime() + (exmin * 60 * 1000));
	var expires = "expires=" + d.toUTCString();
	document.cookie = cname + "=" + cvalue + ";" + expires + ";path=/";
}

// permette di leggere un cookie
function getCookie(cname) {
	var name = cname + "=";
	var ca = document.cookie.split(';');
	for (var i = 0; i < ca.length; i++) {
		var c = ca[i];
		while (c.charAt(0) == ' ') {
			c = c.substring(1);
		}
		if (c.indexOf(name) == 0) {
			return c.substring(name.length, c.length);
		}
	}
	return "";
}

// mostra un messaggio di successo
function showSuccessAlert(data) {
	showAlert('#success', data['message']);
}

// mostra un messaggio d'errore
function showErrorAlert(data) {
	if (data == undefined) {
		showAlert('#error', 'Il server non ha ritornato dati: potrebbe essere offline');
		return;
	}
	showAlert('#error', data['message']);
}

// fa apparire e scomparire automaticamente un alert
function showAlert(id, text) {
	$(id).text(text);
	$(id).fadeTo(3500, 500).slideUp(500, function () {
		$(id).slideUp(500);
		$(id).text("")
	});
}


// esegue alcune operazioni prima di chiudere la pagina.
// In particolare, carica i valori dei campi di input nei tag HTML per poter essere
// trasferiti insieme al resto
function unload() {
	$(document).find('input').attr('value', function () {
		return $(this).val();
	});
	$(document).find('textarea').attr('value', function () {
		return $(this).val();
	});
	
	// non funziona
	/*$(document).find('input[type=checkbox]').prop('checked', function () {
		return $(this).is(':checked');
	});*/
}