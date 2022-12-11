(function(){
    var holdingPhoneContEl = document.getElementById('holding-phone-cont');
    var viewportOffset;

    class ScrollFreezer {
        constructor() {
            this.isEnable = false;
            this.scrollLeft = 0;
            this.scrollTop = null;
            this.timeout = null;
        }

        enable(duration){

            this.isEnable = true;
            // Get the current page scroll position
            // this.scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;
            this.scrollTop = window.pageYOffset || document.documentElement.scrollTop;

            clearTimeout(this.timeout)
            this.timeout = setTimeout(() => {
                freezer.disable()
            }, duration)
        }

        disable(){
            this.isEnable = false
            // this.scrollLeft = null;
            this.scrollTop = null;
        }

        perform(){
            if(this.isEnable){
                let currentPointer = window.pageYOffset || document.documentElement.scrollTop;
                let delta = (currentPointer - this.scrollTop) * 0.57
                this.scrollTop += delta
                window.scrollTo(this.scrollLeft, this.scrollTop);
            }
        }
    }

    var freezer = new ScrollFreezer()

    function handleScrolling() {
        let scrollTop = window.pageYOffset || document.documentElement.scrollTop;

        window.onscroll = function(evt) {

            freezer.perform()

            let currentPointer = window.pageYOffset || document.documentElement.scrollTop;
            if (Math.abs(currentPointer - scrollTop) / scrollTop > 0.01){
                scrollTop = currentPointer;
                localStorage.setItem('scrollTop', scrollTop)
            }
        };
    }

    var parameters = {
        "holding-phone-driver-1-translateY-end": -window.innerHeight * 0.38,
        "holding-phone-driver-left-translateY-end": -window.innerHeight * 0.38 - window.innerHeight * 0.15
    }

    function animationScript(){
        new TheSuperSonicPluginForScrollBasedAnimation({
            drivers: {
                "iphone-logo-driver-1": {
                    properties: {
                        translateY: {
                            start: 0,
                            end: -180,
                            unit: "px",
                            elements: [".iphone-logo-img"],
                        },
                    },
                },
                "iphone-logo-driver-2": {
                    properties: {
                        opacity: {
                            start: 1.0,
                            end: 0.0,
                            elements: [".iphone-logo-img"],
                        },
                    },
                },
                "holding-phone-driver-1": {
                    properties: {
                        translateY: {
                            start: 0,
                            end: parameters['holding-phone-driver-1-translateY-end'],
                            unit: "px",
                            elements: [".right-holds-phone", ".left-holds-phone"],
                        },
                    },
                    hooks: { // property hooks, each hook is optional
                        onAfterRender(property) {
                            if (property.progress > 0.01 ){
                                freezer.enable(10000)
                            }
                        },
                    },
                },
                "left-phone-text-driver": {
                    properties: {
                        scaleX: {
                            start: 0.2,
                            end: 1.05,
                            elements: ["#left-phone-text > div > div", "#right-phone-text > div > div"],
                        },
                        scaleY: {
                            start: 0.4,
                            end: 1.3,
                            elements: ["#left-phone-text > div > div", "#right-phone-text > div > div"],
                        },
                        translateY: {
                            start: 230,
                            end: 0,
                            unit: "px",
                            elements: ["#left-phone-text > div > div", "#right-phone-text > div > div"],
                        },
                    },
                    hooks: { // property hooks, each hook is optional
                        onAfterRender(property) {
                            if (property.progress > 0.55 ){
                                freezer.enable(2000)
                            }
                        },
                    },
                },
                "phone-screen-driver": {
                    properties: {
                        scaleX: {
                            start: 1.05,
                            end: 0.2,
                            elements: ["#left-phone-text > div > div", "#right-phone-text > div > div"],
                        },
                        scaleY: {
                            start: 1.3,
                            end: 0.4,
                            elements: ["#left-phone-text > div > div", "#right-phone-text > div > div"],
                        },
                        translateY: {
                            start: 0,
                            end: 285,
                            unit: "px",
                            elements: ["#left-phone-text > div > div", "#right-phone-text > div > div"],
                        },
                    },
                },
                "holding-phone-driver-left": {
                    properties: {
                        translateY: {
                            start: parameters['holding-phone-driver-1-translateY-end'],
                            end: parameters['holding-phone-driver-left-translateY-end'],
                            unit: "px",
                            elements: [".left-holds-phone"],
                        },
                        translateX: {
                            start: 0,
                            end: -1800,
                            unit: "px",
                            elements: [".left-holds-phone"],
                        },
                        scale: {
                            start: 1,
                            end: 0.55,
                            elements: [".left-holds-phone"],
                        },
                    },
                    hooks: { // property hooks, each hook is optional
                        onAfterRender(property) {
                            if (property.progress < 0.00001 || property.progress >= 0.9999){
                                if(holdingPhoneContEl.style.position === 'fixed'){
                                    holdingPhoneContEl.style.position = '';
                                    freezer.enable(2000)
                                }
                            } else if (holdingPhoneContEl.style.position !== 'fixed') {
                                // To store the position at starting point to use lately in reverse animation
                                // without it holdingPhoneContEl is at very different position because scrolling pointer
                                // has been moved down
                                if (property.progress < 0.5 || !viewportOffset){
                                    viewportOffset = holdingPhoneContEl.getBoundingClientRect();
                                }
                                holdingPhoneContEl.style.position = 'fixed';
                                holdingPhoneContEl.style.top = viewportOffset.top + 'px';
                                holdingPhoneContEl.style.left = 0;
                                holdingPhoneContEl.style.right = 0;
                            }
                        },
                    },
                },
                "holding-phone-driver-right": {
                    properties: {
                        translateY: {
                            start: parameters['holding-phone-driver-1-translateY-end'],
                            end: parameters['holding-phone-driver-left-translateY-end'],
                            unit: "px",
                            elements: [".right-holds-phone"],
                        },
                        translateX: {
                            start: 0,
                            end: 1800,
                            unit: "px",
                            elements: [".right-holds-phone"],
                        },
                        scale: {
                            start: 1,
                            end: 0.55,
                            elements: [".right-holds-phone"],
                        },
                    },
                },
                "battery": {
                    properties: {
                        scale: {
                            start: 1,
                            end: 5.3,
                            elements: ["#battery-cont"],
                        },
                        scaleX: {
                            start: 0,
                            end: 99,
                            unit: '%',
                            elements: ["#battery-logo img:last-child"],
                        },
                        opacity: {
                            start: 0,
                            end: 1.0,
                            elements: ["#battery-cont"],
                        },
                        rotateX: {
                            start: 0,
                            end: 15,
                            unit: 'deg',
                            elements: ["#battery-cont"],
                        },
                        rotateY: {
                            start: 0,
                            end: -28,
                            unit: 'deg',
                            elements: ["#battery-cont"],
                        },
                        rotateZ: {
                            start: 0,
                            end: -7,
                            unit: 'deg',
                            elements: ["#battery-cont"],
                        },
                    },
                },
                "introduction-battery": {
                    properties: {
                        rotateX: {
                            start: 15,
                            end: -8,
                            unit: 'deg',
                            elements: ["#battery-cont"],
                        },
                        rotateY: {
                            start: -28,
                            end: 16,
                            unit: 'deg',
                            elements: ["#battery-cont"],
                        },
                        rotateZ: {
                            start: -7,
                            end: 8,
                            unit: 'deg',
                            elements: ["#battery-cont"],
                        },
                        translateY: {
                            start: 0,
                            end: -650,
                            unit: "px",
                            elements: ["#battery-section"],
                        },
                    }
                },
                "introduction-1": {
                    properties: {
                        translateY: {
                            start: 0,
                            end: -450,
                            unit: "px",
                            elements: ["#introduction-1"],
                        },
                        rotateX: {
                            start: -40,
                            end: 0,
                            unit: 'deg',
                            elements: ["#introduction-1"],
                        },
                        rotateY: {
                            start: 40,
                            end: 0,
                            unit: 'deg',
                            elements: ["#introduction-1"],
                        },
                        scale: {
                            start: 1.1,
                            end: 1,
                            elements: ["#introduction-1"],
                        },
                    },
                },
                "introduction-photo-driver": {
                    properties: {
                        translateX: {
                            start: -10,
                            end: 0,
                            unit: "%",
                            elements: ["#photo"],
                        },
                    }
                },
                "left-phone-text-2-driver": {
                    properties: {
                        translateX: {
                            start: 131,
                            end: -63,
                            unit: "px",
                            elements: ["#left-phone-text-2 > div > div"],
                        },
                    }
                },
                "right-phone-text-2-driver": {
                    properties: {
                        translateX: {
                            start: -188,
                            end: 63,
                            unit: "px",
                            elements: ["#right-phone-text-2 > div > div"],
                        },
                    }
                },
                "left-phone-text-2-driver-2": {
                    properties: {
                        translateX: {
                            start: -63,
                            end: 131,
                            unit: "px",
                            elements: ["#left-phone-text-2 > div > div"],
                        },
                    }
                },
                "right-phone-text-2-driver-2": {
                    properties: {
                        translateX: {
                            start: 63,
                            end: -188,
                            unit: "px",
                            elements: ["#right-phone-text-2 > div > div"],
                        },
                    }
                },
            },
        })
    }

    window.onload = () => {


        animationScript()

        setTimeout(() => {
            var body = document.getElementsByTagName('body')[0]
            var scrollTop = localStorage.getItem('scrollTop', scrollTop)

            body.style.position = 'relative'

            if (scrollTop && scrollTop > 1) {
                window.onscroll = function(evt) {
                    let currentPointer = window.pageYOffset || document.documentElement.scrollTop;

                    if (currentPointer < scrollTop - 50){
                        setTimeout(() => {
                            window.scrollBy({
                                top: 20,
                                left: 0,
                                behavior: 'auto',
                            })
                        }, 10)
                    } else {
                        setTimeout(() => {
                            body.classList.remove('notready')
                            handleScrolling()
                        }, 200)
                    }

                };


                window.scrollBy({
                    top: 5,
                    left: 0,
                    behavior: 'auto',
                })

            } else {
                body.classList.remove('notready')
                handleScrolling()
            }
        }, 500)
    }
})()
