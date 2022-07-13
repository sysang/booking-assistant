let flky = window.flky = new Flickity('#full-width');

// flky.on( 'dragMove', function( event, pointer ) {
//   console.log( event.type, pointer.pageX, pointer.pageY );
// });
flky.on( 'select', function() {
  console.log( 'selected', flky.selectedIndex );
} );

flky.on( 'settle', function() {
  console.log( 'settled', flky.x );
} );
